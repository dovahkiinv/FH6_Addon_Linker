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

### Fixed

- Stabilizuje smoke testy CLI na Windows/Linux, sprawdzając wpis konsolowy przez metadane i wymuszając UTF-8 w procesach potomnych.
