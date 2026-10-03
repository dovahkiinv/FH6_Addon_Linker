# Instrukcja użytkownika

## M0 — szkielet projektu

Ta wersja nie skanuje biblioteki, nie zmienia plików gry i nie udostępnia
jeszcze GUI. Do sprawdzenia pakietu wymagany jest Python 3.11 lub nowszy:

```console
python -m fh6linker --version
```

Aby uruchomić testy deweloperskie:

```console
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pytest -q
```

Instrukcja konfiguracji gry, biblioteki i operacji na modach zostanie dodana
wraz z M1/M2. Nie próbuj używać tego etapu do modyfikowania plików gry.
