"""Typowane raporty przekazywane pomiędzy rdzeniem, CLI i GUI."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlannedAction:
    """Jedna zaplanowana zmiana na pliku."""

    action: str
    mod_name: str
    file: str | None = None
    source: str | None = None
    target: str | None = None
    backup: str | None = None
    size: int = 0
    note: str | None = None


@dataclass
class OperationReport:
    """Wynik lub plan operacji bez zależności od interfejsu."""

    operation: str
    dry_run: bool = False
    actions: list[PlannedAction] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    files_changed: int = 0
    privilege_required: bool = False

    @property
    def files_planned(self) -> int:
        """Liczba plików ujętych w planie."""
        return sum(action.file is not None for action in self.actions)

    @property
    def exit_code(self) -> int:
        """Kod zakończenia CLI: sukces 0, błąd 1, konflikt 2 lub uprawnienia 3."""
        if self.privilege_required:
            return 3
        if self.errors:
            return 1
        if self.conflicts:
            return 2
        return 0

    @property
    def successful(self) -> bool:
        """Informuje, czy operacja zakończyła się bez błędów i konfliktów."""
        return self.exit_code == 0

    def as_dict(self) -> dict[str, Any]:
        """Zwraca przenośną reprezentację JSON raportu."""
        return {
            "operation": self.operation,
            "dry_run": self.dry_run,
            "files_planned": self.files_planned,
            "files_changed": self.files_changed,
            "actions": [asdict(action) for action in self.actions],
            "warnings": list(self.warnings),
            "conflicts": list(self.conflicts),
            "errors": list(self.errors),
            "privilege_required": self.privilege_required,
            "exit_code": self.exit_code,
        }


@dataclass(frozen=True)
class ModStatus:
    """Status pojedynczego moda."""

    mod_id: str
    name: str
    category: str
    status: str
    file_count: int
    broken_count: int = 0
    warnings: tuple[str, ...] = ()


@dataclass
class StatusReport:
    """Zestaw statusów biblioteki wraz z problemami skanowania."""

    mods: list[ModStatus] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Zwraca przenośną reprezentację JSON statusu."""
        return {
            "mods": [asdict(mod) for mod in self.mods],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }
