# Rejestr decyzji projektowych

Nieoczywiste decyzje zapisujemy w formacie ADR: kontekst → decyzja →
konsekwencje.

## ADR-0001: wersja pakietu przed wydaniem 1.0

- **Kontekst:** milestone M0 wymagał działającego `--version`, ale projekt nie
  miał jeszcze funkcji użytkowych.
- **Decyzja:** używamy wersji PEP 440 `0.1.0.dev0`, zdefiniowanej w
  `fh6linker/__init__.py` i powtórzonej w `pyproject.toml`.
- **Konsekwencje:** wersja jest jawnie deweloperska; przed każdym wydaniem
  należy zsynchronizować oba pola i changelog.

## ADR-0002: CI sprawdza oba systemy i dwie wersje Pythona

- **Kontekst:** projekt celuje w Windows oraz Linuksa/SteamOS, a specyfikacja
  wymaga Pythona 3.11+.
- **Decyzja:** CI używa macierzy `ubuntu-latest` i `windows-latest` oraz Pythona
  3.11 i 3.13. Na Linuksie dodatkowo importuje moduły GUI przez `xvfb-run`.
- **Konsekwencje:** regresje zgodności są wykrywane przed scaleniem; test importu
  nie tworzy okna.

## ADR-0003: układ backupów i ochrona historii

- **Kontekst:** jeden target może otrzymać nowy plik waniliowy po aktualizacji
  gry; poprzednia kopia nie może zostać utracona ani pomylona z nową.
- **Decyzja:** aktualny baseline trafia do `backups/files/<ścieżka targetu>`, a
  różniące się kolejne wersje do `backups/history/<znacznik czasu>/<ścieżka>`.
  Konflikty są kopiowane do `backups/conflicts/` i oryginalny plik w grze
  pozostaje nietknięty.
- **Konsekwencje:** backupy mogą zajmować dużo miejsca, ale silnik nie usuwa ich
  automatycznie. Użytkownik widzi ścieżki kopii w raportach.

## ADR-0004: ID moda jest względną ścieżką w bibliotece

- **Kontekst:** dwa różne foldery mogą mieć tę samą nazwę wyświetlaną.
- **Decyzja:** stan zapisuje mod pod ID względnym, np. `Audio/Engine Mod`; CLI
  przy niejednoznacznej nazwie prosi o dokładniejszy identyfikator.
- **Konsekwencje:** przeniesienie moda między kategoriami zmienia jego ID i może
  wymagać ponownego skanu oraz weryfikacji stanu.

## ADR-0005: rollback i samonaprawa z journalu

- **Kontekst:** awaria może nastąpić po backupie, usunięciu oryginału lub
  utworzeniu linku, ale przed zapisem końcowego state.
- **Decyzja:** każdy plik ma zdarzenie `begin` przed modyfikacją, a kolejne fazy
  opisują backup, usunięcie targetu i utworzenie linku. Niezakończone enable/
  repair jest cofane przy następnym statusie/operacji; disable/restore jest
  dokańczane.
- **Konsekwencje:** dziennik jest trwałym elementem stanu i nie jest samoczynnie
  czyszczony. W razie uszkodzenia journalu aplikacja wstrzymuje zmiany.

## ADR-0006: hash i rozmiar kopii zapisujemy w stanie

- **Kontekst:** samo istnienie ścieżki backupu nie wykrywa przypadkowego
  uszkodzenia ani podmiany magazynowanej kopii.
- **Decyzja:** wpis pliku zapisuje dodatkowo `backup_sha256`, `backup_size` i
  `backup_mtime`; odczyt starszego stanu bez tych pól pozostaje obsługiwany.
- **Konsekwencje:** przed disable/restore kopia jest weryfikowana. Zmodyfikowany
  backup blokuje przywracanie, a link w grze pozostaje nietknięty.

## ADR-0007: magazyn backupów nie może uciekać przez symlinki

- **Kontekst:** podkatalog w magazynie może być symlinkiem prowadzącym poza
  wybrany backup root, nawet gdy sama ścieżka konfiguracji jest poprawna.
- **Decyzja:** przed odczytem/zapisem ścieżki backupów są rozwiązywane i
  sprawdzane względem magazynu; weryfikowany jest także domyślny magazyn.
- **Konsekwencje:** symlink wyprowadzający poza magazyn zatrzymuje operację
  przed zmianą plików gry.
