"""Skanowanie biblioteki modów i wykrywanie katalogów docelowych gry."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

ROOT_MARKERS = frozenset({"media", "mediapc", "mediaoverride"})
IGNORED_NAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini", "__macosx"})


@dataclass(frozen=True)
class ModIssue:
    """Problem albo ostrzeżenie wykryte podczas skanowania jednego moda."""

    code: str
    message: str
    path: Path | None = None
    severity: str = "warning"


@dataclass(frozen=True)
class ModFile:
    """Plik źródłowy i jego ścieżka względem katalogu gry."""

    source_path: Path
    target_rel: str
    size: int
    mtime: float


@dataclass(frozen=True)
class ModMetadata:
    """Obsługiwane pola opisowe z opcjonalnego mod.json."""

    display_name: str | None = None
    category: str | None = None
    author: str | None = None
    version: str | None = None
    source_url: str | None = None
    notes: str | None = None
    target_prefix: str = ""
    online_safe: bool | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModMetadata:
        """Waliduje typy pól metadanych bez odrzucania nieznanych kluczy."""
        online_safe = data.get("online_safe")
        if online_safe is not None and not isinstance(online_safe, bool):
            online_safe = None
        text_values = {
            field_name: str(data[field_name]).strip()
            for field_name in (
                "display_name",
                "category",
                "author",
                "version",
                "source_url",
                "notes",
                "target_prefix",
            )
            if data.get(field_name) is not None
        }
        return cls(**text_values, online_safe=online_safe)


@dataclass(frozen=True)
class Mod:
    """Wykryty mod wraz z plikami, kategorią i problemami."""

    mod_id: str
    name: str
    display_name: str
    category: str
    source_root: Path
    moderoot_rel: str
    root_marker: str | None
    files: tuple[ModFile, ...] = ()
    metadata: ModMetadata = field(default_factory=ModMetadata)
    issues: tuple[ModIssue, ...] = ()

    @property
    def valid(self) -> bool:
        """Czy mod ma przynajmniej jeden plik i nie ma błędu struktury."""
        return bool(self.files) and not any(issue.severity == "error" for issue in self.issues)


@dataclass
class ScanResult:
    """Wynik skanowania biblioteki."""

    library_dir: Path
    mods: list[Mod] = field(default_factory=list)
    issues: list[ModIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ModIssue]:
        """Błędy skanowania wymagające uwagi użytkownika."""
        return [issue for issue in self.issues if issue.severity == "error"] + [
            issue for mod in self.mods for issue in mod.issues if issue.severity == "error"
        ]

    @property
    def warnings(self) -> list[ModIssue]:
        """Ostrzeżenia, w tym ignorowane pliki towarzyszące."""
        return [issue for issue in self.issues if issue.severity == "warning"] + [
            issue for mod in self.mods for issue in mod.issues if issue.severity == "warning"
        ]


def scan_library(library_dir: str | Path) -> ScanResult:
    """Wykrywa mody po korzeniach `media`, `mediapc` lub `mediaoverride`.

    Katalogi bez korzenia moda są traktowane jako kategorie i skanowane głębiej.
    Dowiązania symboliczne nie są śledzone, aby skan nie wychodził poza bibliotekę.
    """
    library = Path(library_dir).expanduser().resolve()
    if not library.exists() or not library.is_dir():
        raise ValueError(
            f"Biblioteka modów nie istnieje lub nie jest katalogiem: {library}. "
            "Utwórz folder i uruchom skan ponownie."
        )

    result = ScanResult(library_dir=library)
    visited: set[Path] = set()

    def visit(folder: Path) -> None:
        try:
            resolved = folder.resolve()
            if resolved in visited or not resolved.is_relative_to(library):
                return
            visited.add(resolved)
            children = sorted(folder.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            result.issues.append(
                ModIssue(
                    code="unreadable_directory",
                    message=f"Nie można odczytać katalogu {folder}: {exc}",
                    path=folder,
                    severity="warning",
                )
            )
            return

        marker_dirs = [
            child
            for child in children
            if child.name.casefold() in ROOT_MARKERS
            and child.is_dir()
            and not child.is_symlink()
        ]
        metadata_path = folder / "mod.json"
        has_metadata = not metadata_path.is_symlink() and metadata_path.is_file()
        if marker_dirs or has_metadata:
            result.mods.append(
                _build_mod(
                    library,
                    folder,
                    children,
                    marker_dirs,
                    virtual_root=not marker_dirs,
                )
            )
            return

        for child in children:
            if _is_ignored(child.name) or _is_hidden(child):
                continue
            if child.is_symlink():
                result.issues.append(
                    ModIssue(
                        code="symlink_ignored",
                        message=f"Pominięto dowiązanie poza biblioteką: {child}",
                        path=child,
                    )
                )
            elif child.is_dir():
                visit(child)
            elif child.is_file() and not child.name.startswith("."):
                result.issues.append(
                    ModIssue(
                        code="loose_file_ignored",
                        message=f"Pominięto plik poza rozpoznanym modem: {child}",
                        path=child,
                    )
                )

    visit(library)
    result.mods.sort(key=lambda mod: (mod.category.casefold(), mod.display_name.casefold(), mod.mod_id.casefold()))
    return result


def _build_mod(
    library: Path,
    folder: Path,
    children: list[Path],
    marker_dirs: list[Path],
    *,
    virtual_root: bool = False,
) -> Mod:
    relative_id = folder.relative_to(library).as_posix()
    mod_id = relative_id if relative_id not in {"", "."} else folder.name
    issues: list[ModIssue] = []
    metadata = _read_metadata(folder / "mod.json", issues)
    name = folder.name
    try:
        parent_category = folder.parent.relative_to(library).as_posix()
    except ValueError:
        parent_category = ""
    category = metadata.category or (
        parent_category if parent_category not in {"", "."} else "Bez kategorii"
    )
    display_name = metadata.display_name or name

    for child in children:
        if virtual_root or child in marker_dirs or _is_ignored(child.name) or _is_hidden(child):
            continue
        if child.is_symlink():
            issues.append(
                ModIssue(
                    code="symlink_ignored",
                    message=f"Pominięto dowiązanie w katalogu moda: {child}",
                    path=child,
                )
            )
        elif child.is_file():
            issues.append(
                ModIssue(
                    code="ignored_sidecar",
                    message=f"Plik poza korzeniem gry nie zostanie wdrożony: {child.name}",
                    path=child,
                )
            )
        elif child.is_dir():
            issues.append(
                ModIssue(
                    code="ignored_sidecar_directory",
                    message=f"Katalog poza korzeniem gry nie zostanie wdrożony: {child.name}",
                    path=child,
                )
            )

    if len(marker_dirs) > 1:
        marker_names = ", ".join(marker.name for marker in marker_dirs)
        issues.append(
            ModIssue(
                code="multiple_roots",
                message=(
                    f"Mod ma kilka korzeni ({marker_names}); nie można bezpiecznie "
                    "ustalić struktury. Rozdziel go na osobne mody."
                ),
                path=folder,
                severity="error",
            )
        )
        return Mod(
            mod_id=mod_id,
            name=name,
            display_name=display_name,
            category=category,
            source_root=folder,
            moderoot_rel="",
            root_marker=None,
            metadata=metadata,
            issues=tuple(issues),
        )

    root = folder if virtual_root else marker_dirs[0]
    files: list[ModFile] = []
    targets: set[str] = set()
    _collect_files(
        root,
        "" if virtual_root else root.name,
        files,
        issues,
        ignore_metadata=virtual_root,
    )
    for mod_file in files:
        target_key = mod_file.target_rel.casefold()
        if target_key in targets:
            issues.append(
                ModIssue(
                    code="duplicate_target",
                    message=f"Dwa pliki moda wskazują ten sam cel: {mod_file.target_rel}",
                    path=mod_file.source_path,
                    severity="error",
                )
            )
        targets.add(target_key)

    if not files:
        issues.append(
            ModIssue(
                code="empty_mod",
                message="Mod nie zawiera żadnych plików do wdrożenia.",
                path=root,
                severity="error",
            )
        )

    return Mod(
        mod_id=mod_id,
        name=name,
        display_name=display_name,
        category=category,
        source_root=folder,
        moderoot_rel="" if virtual_root else root.name,
        root_marker=None if virtual_root else root.name,
        files=tuple(files),
        metadata=metadata,
        issues=tuple(issues),
    )


def _collect_files(
    folder: Path,
    target_prefix: str,
    files: list[ModFile],
    issues: list[ModIssue],
    *,
    ignore_metadata: bool = False,
) -> None:
    """Zbiera pliki z korzenia gry, pomijając ukryte i systemowe śmieci."""
    try:
        children = sorted(folder.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        issues.append(
            ModIssue(
                code="unreadable_directory",
                message=f"Nie można odczytać {folder}: {exc}",
                path=folder,
                severity="error",
            )
        )
        return

    for child in children:
        if ignore_metadata and child == folder / "mod.json":
            continue
        if _is_readme(child.name):
            issues.append(
                ModIssue(
                    code="readme_ignored",
                    message=f"Pominięto plik README, który nie zostanie wdrożony: {child}",
                    path=child,
                )
            )
            continue
        if _is_ignored(child.name) or _is_hidden(child):
            continue
        if child.is_symlink():
            issues.append(
                ModIssue(
                    code="symlink_ignored",
                    message=f"Pominięto dowiązanie symboliczne: {child}",
                    path=child,
                )
            )
        elif child.is_dir():
            _collect_files(
                child,
                PurePosixPath(target_prefix, child.name).as_posix(),
                files,
                issues,
            )
        elif child.is_file():
            try:
                stat = child.stat()
            except OSError as exc:
                issues.append(
                    ModIssue(
                        code="unreadable_file",
                        message=f"Nie można odczytać metadanych pliku {child}: {exc}",
                        path=child,
                        severity="error",
                    )
                )
                continue
            files.append(
                ModFile(
                    source_path=child,
                    target_rel=PurePosixPath(target_prefix, child.name).as_posix(),
                    size=stat.st_size,
                    mtime=stat.st_mtime,
                )
            )


def _read_metadata(path: Path, issues: list[ModIssue]) -> ModMetadata:
    if not path.is_file():
        return ModMetadata()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("korzeń mod.json musi być obiektem JSON")
        return ModMetadata.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        issues.append(
            ModIssue(
                code="invalid_metadata",
                message=f"Nie można odczytać {path.name}: {exc}. Mod pozostaje dostępny z nazwą folderu.",
                path=path,
            )
        )
        return ModMetadata()


def _is_readme(name: str) -> bool:
    """Rozpoznaje pliki README, które nie mogą zostać wdrożone do gry."""
    return name.casefold().startswith("readme")


def _is_ignored(name: str) -> bool:
    """Rozpoznaje pliki systemowe i katalogi paczek macOS."""
    return name.casefold() in IGNORED_NAMES


def _is_hidden(path: Path) -> bool:
    """Pomija pliki kropkowe i pliki z atrybutem Hidden w Windows."""
    if path.name.startswith("."):
        return True
    if os.name == "nt":
        try:
            attributes = path.stat(follow_symlinks=False).st_file_attributes
        except OSError:
            return False
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2))
    return False
