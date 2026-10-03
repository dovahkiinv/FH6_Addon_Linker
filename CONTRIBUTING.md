# Współtworzenie projektu

Dziękujemy za zainteresowanie FH6 Addon Linker. Projekt jest rozwijany
milestone'ami opisanymi w `PROMPT.md`; nie implementuj kolejnego etapu, zanim
bieżący nie przejdzie testów i nie zostanie zaktualizowany `CHANGELOG.md`.

## Zasady

- Nie dodawaj zależności runtime. `pytest` i `PyInstaller` są zależnościami
  deweloperskimi.
- Stosuj identyfikatory po angielsku, type hints, `pathlib` i dataclasses w
  wewnętrznym API; docstringi i komunikaty pisz po polsku.
- Każdą nową funkcję pokryj testem w tym samym zestawie zmian.
- Zmiany wykonuj w małych, przeglądalnych PR-ach. Stosuj Conventional Commits,
  np. `feat:`, `fix:`, `docs:`, `test:` lub `chore:`.
- Zapisuj nieoczywiste wybory w `docs/DECISIONS.md`.

## Środowisko deweloperskie

Wymagany Python 3.11 lub nowszy. Z katalogu repozytorium:

```console
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pytest -q
```

Na Linuksie CI sprawdza też import modułów GUI w `xvfb-run`. Kod GUI nie może
blokować głównego wątku aplikacji.
