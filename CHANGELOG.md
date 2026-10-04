# Changelog

Wszystkie istotne zmiany projektu będą opisywane w tym pliku. Format opiera się
na [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) i wersjonowaniu
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Skaner biblioteki po cichu pomija pliki archiwów, aby nie trafiały do ostrzeżeń
  ani listy plików wdrażanych do gry.
- Odświeżony layout GUI: prawie czarna paleta, karty ścieżek i statystyk,
  czytelniejsze akcje i większa przestrzeń na listę modów.
- Przyciski „Otwórz folder” przy ścieżkach gry, biblioteki i kopii, akcja
  „Włącz wszystkie” z planem zatwierdzenia oraz przełącznik Polski/English
  zapamiętywany między uruchomieniami.
- Konfiguracja PyInstaller one-file/windowed, zależność budowania w
  `requirements-build.txt`, skrypt `scripts/build_exe.ps1` i workflow GitHub
  Actions budujący Windowsowy EXE oraz portable ZIP.
- GUI M2 tkinter/ttk: ciemny motyw, czytelny stan pustej biblioteki, kreator
  konfiguracji, lista modów z filtrem i checkboxami, plan przed zmianami, postęp,
  dziennik i tryb przywracania backupów; konflikty pozostają bez zmian.
- Zabezpieczenie kreatora przed zmianą ścieżek gry, biblioteki lub backupów,
  gdy istnieją wdrożone pliki, oraz blokowanie wyboru podczas pracy w tle.
- Uruchamianie GUI przez `python -m fh6linker gui` i Windowsowy launcher
  `FH6AddonLinker.pyw`; CLI pozostaje pomocnicze, a build `.exe` obsługuje PyInstaller.
- Szkielet pakietu Python `fh6linker` i uruchamialne polecenie `--version`.
- Konfigurację projektu, zależności deweloperskie, testy smoke i CI dla Linuxa
  oraz Windowsa na Pythonie 3.11, 3.13 i 3.14.
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

- Przy odpowiedniku pliku pod drugim korzeniem `media`/`mediapc` plan pokazuje
  ostrzeżenie, ale pozwala zatwierdzić target wskazany przez moda; backup obejmuje
  wyłącznie plik istniejący dokładnie pod tym targetem.
- Ustawia ciemne tło również dla zwykłych ramek kreatora/dialogów, które na
  części platform wcześniej mogły odziedziczyć jasny kolor motywu systemowego.
- Stabilizuje smoke testy CLI na Windows/Linux, sprawdzając wpis konsolowy przez metadane i wymuszając UTF-8 w procesach potomnych.
