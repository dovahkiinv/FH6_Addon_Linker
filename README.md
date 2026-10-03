# FH6 Addon Linker

Narzędzie do zarządzania modami Forza Horizon 6 przez odwracalne linkowanie
plików z zewnętrznej biblioteki. **Docelowym produktem jest aplikacja GUI dla
Windows spakowana do `.exe`; CLI jest interfejsem pomocniczym.** Projekt jest
rozwijany etapami zgodnie ze specyfikacją w `PROMPT.md`.

> **Stan: M1 — rdzeń i CLI.** Można skonfigurować ścieżki, skanować bibliotekę,
> włączać/wyłączać mody i przywracać backupy z CLI. GUI i plik `.exe` nie są
> jeszcze dostępne. Nie uruchamiaj poniższych poleceń modyfikujących gry, jeśli
> nie rozumiesz skutków; najpierw używaj `--dry-run`.

## Ostrzeżenie — regulamin i bany

Modyfikowanie plików gry może naruszać regulamin FH6 i może skutkować banem,
w tym w trybach multiplayer, Festival Playlist i Eliminator. Narzędzie nie
może zagwarantować bezpieczeństwa żadnego moda ani konta. Przed grą online
należy przywrócić pełną wanilię (`fh6linker restore --yes`). Aplikacja nie jest
powiązana z Playground Games, Xbox ani Microsoft. Szczegóły opisuje
[docs/RISKS.md](docs/RISKS.md).

## Uruchomienie CLI (M1)

Wymagany Python 3.11 lub nowszy. W repozytorium:

```console
python -m pip install -e .
python -m fh6linker --version
```

Przykładowy przebieg (ścieżki podmień na swoje; foldery muszą istnieć):

```console
fh6linker set --game "C:\Games\ForzaHorizon6" --library "D:\FH6Mods" --method auto
fh6linker scan
fh6linker enable "Engine Mod" --dry-run
fh6linker enable "Engine Mod"
fh6linker status
fh6linker disable "Engine Mod"
fh6linker restore --yes
```

Biblioteka musi leżeć poza folderem gry. Hardlink działa najlepiej, gdy gra i
biblioteka są na tym samym wolumenie. Mod powinien mieć korzeń `media`,
`mediapc` lub `mediaoverride`, np. `D:\FH6Mods\Audio\Engine Mod\media\Audio\...`.

Do uruchomienia testów deweloperskich:

```console
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Pełniejsze instrukcje: [docs/USAGE.md](docs/USAGE.md).

## Plan rozwoju

- **M0** — szkielet repozytorium i CI.
- **M1** — rdzeń odwracalnego linkowania oraz CLI (bieżący etap).
- **M2** — GUI tkinter/ttk, kreator i obsługa bez CLI.
- **M3** — profile, import paczek, metadane, undo i verify.
- **M4** — pakowanie GUI do portable `.exe`.
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

FH6 Addon Linker is a reversible FH6 mod-linking utility. **The intended end
product is a Windows GUI packaged as an `.exe`; the CLI is a supporting
interface.** The project is currently at **M1**: the core and CLI can configure
paths, scan a library, deploy/disable mods, and restore backups. The GUI and
Windows executable are not available yet.

**Warning:** modifying game files may violate the FH6 terms and may lead to a
ban in multiplayer, Festival Playlist, or Eliminator. The tool cannot guarantee
that a mod or account is safe. Restore a vanilla setup before online play. See
[docs/RISKS.md](docs/RISKS.md) for details.

Requires Python 3.11 or later. Install the development package with
`python -m pip install -e .`; check it with `python -m fh6linker --version`.
Run `fh6linker <command> --help` for CLI options. The roadmap is M2 (GUI), M3
(profiles and import), M4 (portable EXE), M5 (hardening), and M6 (v1.0.0).
See `PROMPT.md` for the complete requirements.
