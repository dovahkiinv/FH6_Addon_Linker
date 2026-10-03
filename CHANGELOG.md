# Changelog

Wszystkie istotne zmiany projektu będą opisywane w tym pliku. Format opiera się
na [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) i wersjonowaniu
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Szkielet pakietu Python `fh6linker` i uruchamialne polecenie `--version`.
- Konfigurację projektu, zależności deweloperskie, testy smoke i CI dla Linuxa
  oraz Windowsa na Pythonie 3.11 i 3.13.
- Początkową dokumentację projektu i ostrzeżeń bezpieczeństwa.
- Rdzeń M1: walidację ścieżek i autodetekcję Steam/Xbox, skanowanie modów,
  bezpieczne hardlinki/symlinki/kopie, atomowy stan, journal WAL i lock.
- CLI `set`, `autodetect`, `scan`, `status`, `enable`, `disable`, `repair`,
  `verify`, `restore` i `doctor`, z planem `--dry-run` oraz raportami JSON.
- Weryfikację hashy/rozmiaru backupów przed przywracaniem, atomowe kopiowanie
  bez nadpisywania oraz ochronę przed symlinkami backupu wychodzącymi poza magazyn.
- Bezpieczne przekazywanie targetu przez `--force` z zachowaniem oryginalnego
  backupu i odtworzeniem poprzedniego właściciela po rollbacku.
- Kod wyjścia 3, gdy operacja wymaga uprawnień administratora.
- Obsługę modów virtual-root z `mod.json` oraz pomijanie README nawet wewnątrz
  korzeni gry.
- Testy rdzenia oraz demo end-to-end dla Linuxa i Windows.

### Fixed

- Stabilizuje smoke testy CLI na Windows/Linux, sprawdzając wpis konsolowy przez metadane i wymuszając UTF-8 w procesach potomnych.
