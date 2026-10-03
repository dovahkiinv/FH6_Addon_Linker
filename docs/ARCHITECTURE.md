# Architektura

Docelowy podział odpowiedzialności opisuje `PROMPT.md`. Aplikacja będzie
zbudowana ze standardowej biblioteki Pythona: warstwa GUI (`tkinter/ttk`), CLI
(`argparse`) oraz wspólny rdzeń niezależny od interfejsu.

## Moduły

- `paths.py` — wykrywanie instalacji i walidacja ścieżek.
- `scanner.py` — skan biblioteki i rozpoznawanie korzeni modów.
- `linkops.py` — hardlink, symlink, kopia oraz weryfikacja własności pliku.
- `state.py` — atomowy stan, dziennik write-ahead i blokada.
- `engine.py` — planowanie i wykonanie operacji.
- `report.py` — typowane raporty współdzielone przez CLI i GUI.
- `importer.py` — import archiwów.
- `gui/` — okno główne, kreator, dialogi i motyw.

## Stan M0

Na tym etapie istnieją importowalne moduły-szkielety oraz CLI z `--version`.
Nie są jeszcze wykonywane operacje na dysku ani skanowanie gry. Każda kolejna
warstwa będzie dodawana wraz z testami zgodnie z kolejnością milestone'ów.
