# Rejestr decyzji projektowych

Nieoczywiste decyzje zapisujemy w formacie ADR: kontekst → decyzja →
konsekwencje.

## ADR-0001: wersja pakietu przed wydaniem 1.0

- **Kontekst:** milestone M0 wymaga działającego `--version`, ale projekt nie
  ma jeszcze funkcji użytkowych.
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
  M0 nie tworzy okna i nie wymaga jeszcze systemowych bibliotek Tk.
