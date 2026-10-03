# FH6 Addon Linker

Narzędzie do zarządzania modami Forza Horizon 6 przez odwracalne linkowanie
plików z zewnętrznej biblioteki. **Docelowym produktem jest aplikacja GUI dla
Windows spakowana do `.exe`; CLI jest interfejsem pomocniczym.** Projekt jest
rozwijany etapami zgodnie ze specyfikacją w `PROMPT.md`.

> **Stan: M2 — GUI desktopowe i rdzeń.** Zwykłe użycie jest dostępne przez
> graficzne okno tkinter/ttk; CLI pozostaje narzędziem pomocniczym. Pakowany
> Windows `.exe` pojawi się w M4. Przed każdą zmianą GUI pokazuje plan do
> zatwierdzenia.

## Ostrzeżenie — regulamin i bany

Modyfikowanie plików gry może naruszać regulamin FH6 i może skutkować banem,
w tym w trybach multiplayer, Festival Playlist i Eliminator. Narzędzie nie
może zagwarantować bezpieczeństwa żadnego moda ani konta. Przed grą online
użyj przycisku GUI **Tryb online · przywróć backupy** (lub CLI
`fh6linker restore --yes`). Narzędzie przywraca wyłącznie pliki zarządzane;
obce lub zmienione pliki pozostawia bez zmian, więc w razie potrzeby sprawdź
integralność gry w Xbox/Steam. Aplikacja nie jest powiązana z Playground Games,
Xbox ani Microsoft. Szczegóły opisuje
[docs/RISKS.md](docs/RISKS.md).

## Uruchomienie GUI (M2)

Wymagany Python 3.11 lub nowszy z tkinter (na Windowsie jest częścią
standardowej instalacji Pythona). Pobierz repozytorium i uruchom
`FH6AddonLinker.pyw` dwuklikiem — otworzy okno bez konsoli. Alternatywnie z
PowerShella:

```powershell
py -3.11 -m pip install -e .
py -3.11 -m fh6linker gui
```

Przy pierwszym uruchomieniu kreator poprosi o folder gry i bibliotekę modów.
W oknie zaznacz mody, kliknij **Zastosuj zaznaczone**, sprawdź plan i dopiero
potem zatwierdź zmianę. Przycisk **Tryb online · przywróć backupy** przygotowuje
plan przywrócenia oryginałów dla plików zarządzanych przez aplikację. Konflikty
pozostawia bez zmian; użyj weryfikacji plików Xbox/Steam, jeśli potrzeba.

Plik `.exe` nie jest jeszcze dostępny — jego pakowanie zaplanowano na M4.

## CLI pomocnicze

Polecenia tekstowe są przeznaczone do diagnostyki i automatyzacji, nie do
codziennego zarządzania modami. Przykładowo:

```console
fh6linker --version
fh6linker scan
fh6linker enable "Engine Mod" --dry-run
fh6linker doctor
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
- **M1** — rdzeń odwracalnego linkowania oraz CLI.
- **M2** — GUI tkinter/ttk, kreator i obsługa bez CLI (bieżący etap).
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
interface.** The project is currently at **M2**: the desktop GUI can configure
paths, scan a library, select mods, preview changes, deploy/disable mods, and
restore backups. The standalone Windows executable is planned for M4.

**Warning:** modifying game files may violate the FH6 terms and may lead to a
ban in multiplayer, Festival Playlist, or Eliminator. The tool cannot guarantee
that a mod or account is safe. Restore the tool-managed backups before online
play, then verify game files with Xbox/Steam if needed; unowned files remain
untouched. See [docs/RISKS.md](docs/RISKS.md) for details.

Requires Python 3.11 or later with tkinter. On Windows, double-click
`FH6AddonLinker.pyw` to open the GUI without a console, or run
`python -m fh6linker gui`. The roadmap is M3 (profiles and import), M4 (portable
EXE), M5 (hardening), and M6 (v1.0.0). CLI options are documented in
`docs/USAGE.md`.
See `PROMPT.md` for the complete requirements.
