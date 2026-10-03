# Architektura

Aplikacja jest podzielona na CLI oraz wspólny rdzeń domenowy; GUI będzie
wykorzystywać ten sam silnik bez własnej implementacji logiki plików. Runtime
korzysta wyłącznie ze standardowej biblioteki Pythona.

## Moduły

- `paths.py` — wykrywanie instalacji, walidacja granic i test działania gry.
- `scanner.py` — skan biblioteki, rozpoznawanie korzeni/virtual-root modów i ostrzeżenia.
- `linkops.py` — hardlink, symlink, kopia, hash i weryfikacja własności targetu.
- `state.py` — konfiguracja, state, atomowe zapisy, write-ahead journal i lock.
- `engine.py` — planowanie, deploy/disable/restore, status, repair i verify.
- `report.py` — typowane raporty współdzielone przez CLI i GUI.
- `cli.py` — parser, tekstowe/JSON raporty i kody wyjścia.
- `importer.py` oraz `gui/` — kolejne etapy rozwoju.

## Przepływ wdrożenia

1. Skaner wyznacza źródłowe pliki moda oraz ścieżki względne wobec gry.
2. Silnik buduje plan, rozwiązuje konflikty, waliduje targety i wolne miejsce.
3. Dziennik zapisuje zamiar przed modyfikacją.
4. Oryginał jest kopiowany do magazynu backupów i weryfikowany SHA-256.
5. Linker tworzy hardlink/symlink albo awaryjną kopię.
6. Stan zapisuje metodę, hashe źródła i wdrożenia oraz ścieżkę backupu z hashem,
   rozmiarem i czasem modyfikacji kopii.
7. `disable` usuwa tylko potwierdzony link i przywraca zweryfikowany backup bez
   nadpisania istniejącego pliku; obcy plik pozostaje nienaruszony i jest
   raportowany jako konflikt.

## Stan M1

Działa CLI i rdzeń `paths`, `scanner`, `linkops`, `state`, `engine`, `report`.
Operacje enable/disable/restore mają plan, dziennik WAL i blokadę instancji.
Na Linuksie i Windowsie testowane są rdzeń oraz CLI. GUI i `.exe` nie są jeszcze
zaimplementowane.
