# Architektura

Aplikacja jest podzielona na GUI, CLI pomocnicze i wspólny rdzeń domenowy.
Oba interfejsy korzystają z tego samego silnika, bez osobnej logiki operacji
plikowych w widoku. Runtime korzysta wyłącznie ze standardowej biblioteki
Pythona (GUI wymaga tkinter).

## Moduły

- `paths.py` — wykrywanie instalacji, walidacja granic i test działania gry.
- `scanner.py` — skan biblioteki, rozpoznawanie korzeni/virtual-root modów i ostrzeżenia.
- `linkops.py` — hardlink, symlink, kopia, hash i weryfikacja własności targetu.
- `state.py` — konfiguracja, state, atomowe zapisy, write-ahead journal i lock.
- `engine.py` — planowanie, deploy/disable/restore, status, repair i verify.
- `report.py` — typowane raporty współdzielone przez CLI i GUI.
- `cli.py` — parser, tekstowe/JSON raporty i kody wyjścia.
- `gui/` — kreator ustawień, główne okno, dialogi i styl M2.
- `importer.py` — kolejne etapy importu paczek.

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

## Stan M2 / pakowanie M4

Działa rdzeń, CLI pomocnicze i GUI tkinter/ttk: kreator ścieżek, lista modów,
filtr, wybór, plany operacji, postęp, dziennik i przywracanie kopii oryginałów
zarządzanych plików. Konflikty pozostają nietknięte. Przy rozbieżności `media` /
`mediapc` silnik nie tworzy równoległego targetu, jeśli dokładny oryginał leży
pod drugim korzeniem. Operacje na plikach wykonuje wspólny silnik z journalingiem
WAL i blokadą instancji.

Konfiguracja PyInstaller (`packaging/FH6AddonLinker.spec`), skrypt PowerShell i
workflow Windows budują samodzielny, jednoplikowy EXE bez konsoli. Budowanie
musi odbywać się na Windowsie; podpis cyfrowy wydania nie jest jeszcze
konfigurowany.
