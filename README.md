# FH6 Addon Linker

Narzędzie desktopowe dla Windows do zarządzania modami FH6 przez odwracalne
linkowanie plików z zewnętrznej biblioteki. Projekt jest rozwijany etapami,
zgodnie ze specyfikacją i kryteriami akceptacji w `PROMPT.md`.

> **Stan: M0 — szkielet repozytorium.** Na tym etapie działa wyłącznie
> identyfikacja wersji i szkielet CLI. Skanowanie, modyfikowanie plików gry,
> GUI, profile i przywracanie kopii zapasowych nie są jeszcze zaimplementowane.

## Ostrzeżenie — regulamin i bany

Modyfikowanie plików gry może naruszać regulamin FH6 i może skutkować banem,
w tym w trybach multiplayer, Festival Playlist i Eliminator. Narzędzie nie
może zagwarantować bezpieczeństwa żadnego moda ani konta. Przed grą online
należy korzystać z pełnej wanilii; planowany profil `WANILLA` ma służyć do
wyłączenia modów. Aplikacja nie jest powiązana z Playground Games, Xbox ani
Microsoft. Szczegóły i pozostałe zagrożenia opisuje [docs/RISKS.md](docs/RISKS.md).

## Szybki start (M0)

Wymagany Python 3.11 lub nowszy:

```console
python -m fh6linker --version
```

Instalacja poleceń deweloperskich i uruchomienie testów:

```console
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pytest -q
fh6linker --version
```

Instrukcje dla bieżącego etapu: [docs/USAGE.md](docs/USAGE.md).

## Plan rozwoju

- **M0** — szkielet repozytorium i CI (ten etap).
- **M1** — rdzeń odwracalnego linkowania oraz CLI.
- **M2** — GUI tkinter/ttk.
- **M3** — profile, import paczek, metadane, undo i verify.
- **M4** — pakowanie i wydanie portable.
- **M5** — utwardzanie, diagnostyka i wydajność.
- **M6** — dokumentacja i wydanie 1.0.0.

Każdy etap ma osobne kryteria akceptacji w `PROMPT.md`. Aktualny zakres zmian
znajduje się w [CHANGELOG.md](CHANGELOG.md).

## Wkład

Zasady pracy nad projektem opisuje [CONTRIBUTING.md](CONTRIBUTING.md). Kod i
identyfikatory są po angielsku, a docstringi, komunikaty i dokumentacja — po
polsku. W runtime nie będą używane zewnętrzne zależności.

---

## English

FH6 Addon Linker is a planned Windows desktop utility for managing FH6 mods
through reversible links to an external library. It is currently at **M0**:
only the package skeleton and version command are implemented. No game files are
scanned or changed yet; the GUI and mod-management features are not available.

**Warning:** modifying game files may violate the FH6 terms and may lead to a
ban in multiplayer, Festival Playlist, or Eliminator. The tool cannot guarantee
that a mod or account is safe. Use a vanilla game setup for online play. See
[docs/RISKS.md](docs/RISKS.md) for details.

Requires Python 3.11 or later. Check the current scaffold with
`python -m fh6linker --version`. The project roadmap is M0 (scaffold), M1 (core
and CLI), M2 (GUI), M3 (profiles and import), M4 (packaging), M5 (hardening),
and M6 (v1.0.0 release). See `PROMPT.md` for the complete requirements.
