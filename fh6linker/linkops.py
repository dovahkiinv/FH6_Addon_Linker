"""Hardlinki, symlinki, kopie i weryfikacja własności plików stagingu."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

LINK_METHODS = frozenset({"auto", "hardlink", "symlink", "copy"})


class LinkOperationError(OSError):
    """Błąd tworzenia linku albo bezpiecznego kopiowania pliku."""

    def __init__(self, message: str, *, requires_privilege: bool = False) -> None:
        super().__init__(message)
        self.requires_privilege = requires_privilege


@dataclass(frozen=True)
class FileDigest:
    """Hash SHA-256, rozmiar i czas modyfikacji pliku."""

    sha256: str
    size: int
    mtime: float


def digest_file(path: str | Path) -> FileDigest:
    """Liczy SHA-256 strumieniowo i odczytuje metadane pliku."""
    file_path = Path(path)
    try:
        hasher = hashlib.sha256()
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(block)
        stat_result = file_path.stat()
    except OSError as exc:
        raise LinkOperationError(f"Nie można odczytać pliku {file_path}: {exc}") from exc
    return FileDigest(
        sha256=hasher.hexdigest(),
        size=stat_result.st_size,
        mtime=stat_result.st_mtime,
    )


def create_link(source: str | Path, target: str | Path, method: str) -> tuple[str, list[str]]:
    """Tworzy hardlink, symlink lub kopię; `auto` próbuje metody po kolei."""
    src = Path(source)
    dst = Path(target)
    selected = method.casefold()
    if selected not in LINK_METHODS:
        raise LinkOperationError(
            f"Nieznana metoda linkowania: {method}. Wybierz auto, hardlink, symlink lub copy."
        )
    if not src.is_file():
        raise LinkOperationError(f"Plik moda nie istnieje lub nie jest zwykłym plikiem: {src}")
    if dst.exists() or dst.is_symlink():
        raise LinkOperationError(f"Plik docelowy już istnieje; nie nadpisuję go: {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)

    attempts = ("hardlink", "symlink", "copy") if selected == "auto" else (selected,)
    failures: list[str] = []
    for candidate in attempts:
        try:
            if candidate == "hardlink":
                os.link(src, dst)
            elif candidate == "symlink":
                dst.symlink_to(src)
            else:
                copy_file_atomic(src, dst, overwrite=False)
            warnings = [
                f"Metoda {failed} nie powiodła się: {message}"
                for failed, message in _pairs(failures)
            ]
            if candidate == "copy":
                warnings.append(
                    "Użyto kopii pliku; zajmuje dodatkowe miejsce i nie współdzieli danych z biblioteką."
                )
            return candidate, warnings
        except OSError as exc:
            reason = _explain_method_failure(candidate, src, dst, exc)
            failures.extend([candidate, reason])
            if selected != "auto":
                is_permission = candidate == "symlink" and _is_permission_error(exc)
                raise LinkOperationError(reason, requires_privilege=is_permission) from exc
    details = "; ".join(
        f"{method_name}: {reason}" for method_name, reason in _pairs(failures)
    )
    raise LinkOperationError(
        "Nie udało się utworzyć żadnego rodzaju linku ani kopii. "
        f"Szczegóły: {details}. Sprawdź uprawnienia i wolne miejsce."
    )


def is_owned(
    target: str | Path,
    source: str | Path,
    method: str,
    expected_sha256: str,
    expected_size: int,
) -> bool:
    """Potwierdza, że plik docelowy nadal należy do wdrożenia narzędzia."""
    dst = Path(target)
    src = Path(source)
    if not dst.exists() and not dst.is_symlink():
        return False
    if dst.is_symlink():
        try:
            if dst.resolve(strict=False) == src.resolve(strict=False):
                return True
        except OSError:
            return False
        return False
    if src.exists():
        try:
            if os.path.samefile(dst, src):
                return True
        except OSError:
            pass
    # Hash/rozmiar jest fallbackiem dla pliku zastąpionego po wdrożeniu,
    # np. gdy ścieżka źródłowa zmieniła inode albo Windows nie udostępnia inode.
    try:
        if dst.is_file() and dst.stat().st_size == expected_size:
            return digest_file(dst).sha256 == expected_sha256
    except OSError:
        return False
    return False


def remove_if_owned(
    target: str | Path,
    source: str | Path,
    method: str,
    expected_sha256: str,
    expected_size: int,
) -> bool:
    """Usuwa target tylko po potwierdzeniu jego własności przez narzędzie."""
    dst = Path(target)
    if not is_owned(dst, source, method, expected_sha256, expected_size):
        return False
    try:
        dst.unlink()
    except OSError as exc:
        raise LinkOperationError(
            f"Nie można usunąć własnego linku {dst}: {exc}. "
            "Zamknij programy blokujące plik i spróbuj ponownie."
        ) from exc
    return True


def copy_file_atomic(
    source: str | Path,
    destination: str | Path,
    *,
    overwrite: bool = True,
    expected_sha256: str | None = None,
    expected_size: int | None = None,
) -> FileDigest:
    """Kopiuje atomowo, opcjonalnie bez nadpisania i z wymaganą sumą kontrolną."""
    src = Path(source)
    dst = Path(destination)
    if not src.is_file():
        raise LinkOperationError(f"Plik źródłowy nie istnieje: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{dst.name}.", suffix=".tmp", dir=dst.parent
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        shutil.copy2(src, temporary)
        source_digest = digest_file(src)
        copied_digest = digest_file(temporary)
        if (
            source_digest.sha256 != copied_digest.sha256
            or source_digest.size != copied_digest.size
        ):
            raise LinkOperationError(
                f"Kopia {src} nie przeszła weryfikacji SHA-256. "
                "Źródło mogło zmienić się podczas kopiowania; ponów operację."
            )
        if (
            (expected_sha256 is not None and source_digest.sha256 != expected_sha256)
            or (expected_size is not None and source_digest.size != expected_size)
        ):
            raise LinkOperationError(
                f"Kopia {src} nie zgadza się z zapisaną sumą kontrolną lub rozmiarem. "
                "Nie zapisano jej w miejscu docelowym."
            )
        if overwrite:
            os.replace(temporary, dst)
            temporary = None
        else:
            try:
                # Twardy link pliku tymczasowego daje atomowe create-if-absent.
                os.link(temporary, dst)
            except FileExistsError:
                raise
            except OSError:
                # Awaryjnie twórz cel wyłącznie przez O_EXCL; nigdy nie nadpisuj.
                descriptor = os.open(dst, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o666)
                identity = os.fstat(descriptor)
                try:
                    with os.fdopen(descriptor, "wb") as output, temporary.open("rb") as input_file:
                        shutil.copyfileobj(input_file, output)
                        output.flush()
                        os.fsync(output.fileno())
                    shutil.copystat(temporary, dst)
                    copied_target = digest_file(dst)
                    if (
                        copied_target.sha256 != source_digest.sha256
                        or copied_target.size != source_digest.size
                    ):
                        raise LinkOperationError(
                            f"Kopia do {dst} nie przeszła weryfikacji SHA-256."
                        )
                except BaseException:
                    try:
                        current = dst.stat()
                        if current.st_dev == identity.st_dev and current.st_ino == identity.st_ino:
                            dst.unlink()
                    except OSError:
                        pass
                    raise
            temporary.unlink(missing_ok=True)
            temporary = None
        return digest_file(dst)
    except LinkOperationError:
        raise
    except OSError as exc:
        raise LinkOperationError(f"Nie można bezpiecznie skopiować {src} do {dst}: {exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _explain_method_failure(method: str, source: Path, target: Path, exc: OSError) -> str:
    if method == "hardlink" and (
        getattr(exc, "errno", None) == getattr(os, "EXDEV", 18)
        or getattr(exc, "winerror", None) == 17
    ):
        return (
            f"Nie mogę utworzyć hardlinku między różnymi wolumenami ({source} → {target}). "
            "Przenieś bibliotekę na ten sam dysk co gra albo użyj metody auto."
        )
    if method == "symlink" and _is_permission_error(exc):
        return (
            "Nie mogę utworzyć symlinku: Windows wymaga uprawnień administratora lub Trybu "
            "dewelopera. Włącz Tryb dewelopera albo użyj metody auto/copy."
        )
    if method == "copy" and getattr(exc, "errno", None) == 28:
        return "Brak miejsca na kopię pliku. Zwolnij miejsce na dysku docelowym i spróbuj ponownie."
    return f"Nie mogę utworzyć {method}: {exc}. Sprawdź uprawnienia i dostępność dysku."


def _is_permission_error(exc: OSError) -> bool:
    return getattr(exc, "winerror", None) in {5, 1314} or getattr(exc, "errno", None) in {
        1,
        13,
    }


def _pairs(items: list[str]) -> list[tuple[str, str]]:
    return [(items[index], items[index + 1]) for index in range(0, len(items), 2)]
