# FH6 Addon Linker

Narzędzie do zarządzania modami Forza Horizon 6 przez odwracalne linkowanie
plików z zewnętrznej biblioteki. **Docelowym produktem jest aplikacja GUI dla
Windows spakowana do `.exe`; CLI jest interfejsem pomocniczym.** Projekt jest
rozwijany etapami zgodnie ze specyfikacją w `PROMPT.md`.

> **Stan: M2 + przygotowane pakowanie M4.** Zwykłe użycie jest dostępne przez
> graficzne okno tkinter/ttk w prawie czarnym motywie; CLI pozostaje narzędziem
> pomocniczym. Repozytorium zawiera skrypt i workflow do zbudowania Windows `.exe`;
> gotowy plik trzeba zbudować na Windowsie. Przed każdą zmianą GUI pokazuje plan
> do zatwierdzenia.

## Ostrzeżenie — regulamin i bany

Modyfikowanie plików gry może naruszać regulamin FH6 i może skutkować banem,
w tym w trybach multiplayer, Festival Playlist i Eliminator. Narzędzie nie
może zagwarantować bezpieczeństwa żadnego moda ani konta. Przed grą online
użyj przycisku GUI **Tryb online** (lub CLI
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
py -3 -m pip install -e .
py -3 -m fh6linker gui
```

Przy pierwszym uruchomieniu kreator poprosi o folder gry i bibliotekę modów.
W oknie zaznacz mody, kliknij **Zastosuj zaznaczone**, sprawdź plan i dopiero
potem zatwierdź zmianę. Przycisk **Tryb online** przygotowuje plan
przywrócenia oryginałów dla plików zarządzanych przez aplikację. Kopia obejmuje
wyłącznie istniejący plik pod dokładnym targetem — nie całą grę ani odpowiednik
w drugim drzewie `media`/`mediapc`. Konflikty pozostają bez zmian; użyj
weryfikacji plików Xbox/Steam, jeśli potrzeba.

## Samodzielny plik `.exe` dla Windows

Budowanie wykonuj na Windowsie (PyInstaller nie tworzy Windowsowego EXE z
Linuksa/macOS). Zainstaluj Python 3.11+ 64-bit, otwórz PowerShell w katalogu
repozytorium i uruchom:

```powershell
py -3 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

Gotowy plik powstanie w `dist\FH6_Addon_Linker.exe`. Jest to pojedynczy program
graficzny z dołączonym Pythonem i tkinter — na komputerze docelowym Python nie
jest potrzebny. Konfiguracja i kopie oryginałów pozostają w profilu użytkownika,
więc można przenieść EXE bez utraty stanu. Alternatywnie workflow **Windows
executable** w GitHub Actions zbuduje EXE i ZIP z instrukcją; uruchom go przez
**Actions → Windows executable → Run workflow** albo wypchnij tag `v*`.

Plik nie jest podpisany certyfikatem wydawcy — Windows może pokazać ostrzeżenie
SmartScreen. Podpis cyfrowy wymaga osobnego certyfikatu code-signing.

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
- **M4** — portable `.exe`; skrypt budujący i workflow Windows są już w repozytorium.
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
interface.** The project is at **M2 with Windows packaging support**: the desktop GUI can
configure paths, scan a library, select mods, preview changes,
deploy/disable mods, and restore originals. A PyInstaller one-file build script
and GitHub Actions workflow are included; build on Windows, since PyInstaller
does not cross-compile Windows executables from Linux/macOS.

**Warning:** modifying game files may violate the FH6 terms and may lead to a
ban in multiplayer, Festival Playlist, or Eliminator. The tool cannot guarantee
that a mod or account is safe. Restore the tool-managed backups before online
play, then verify game files with Xbox/Steam if needed; unowned files remain
untouched. See [docs/RISKS.md](docs/RISKS.md) for details.

Running from source requires Python 3.11 or later with tkinter. On Windows,
double-click `FH6AddonLinker.pyw` to open the GUI without a console, or run
`python -m fh6linker gui`. The standalone EXE includes Python and does not need
a separate installation; build it on Windows with `scripts/build_exe.ps1` or use
the GitHub Actions workflow. The roadmap is M3 (profiles and import), M4
(portable EXE), M5 (hardening), and M6 (v1.0.0). CLI options are documented in
`docs/USAGE.md`. See `PROMPT.md` for the complete requirements.
