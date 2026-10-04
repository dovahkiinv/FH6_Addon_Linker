# FH6 Addon Linker — specyfikacja i polecenie dla agenta kodującego

## Jak używać

Implementuj po jednym milestone na raz, zgodnie z poleceniem użytkownika. Po każdym etapie zaktualizuj `CHANGELOG.md`, pokaż diff i wyniki testów, a potem zatrzymaj się i czekaj na zgodę przed rozpoczęciem następnego milestone'u.

## 0. Rola i cel

Zbuduj FH6 Addon Linker — narzędzie desktopowe dla Windows, działające również na Linuksie/SteamOS, do zarządzania modami Forza Horizon 6 według modelu MSFS Addons Linker:

- biblioteka modów znajduje się poza folderem gry i może mieć dowolnie zagnieżdżone kategorie;
- włączenie moda tworzy link z folderu gry do biblioteki bez kopiowania plików, jeśli to możliwe;
- wyłączenie usuwa wyłącznie link należący do narzędzia i przywraca oryginalny plik z magazynu kopii;
- profile (np. `WANILLA`, `Online`, `Grafika`, `Photo`) przełączają całe zestawy;
- kluczowym elementem jest odwracalny backup/restore, wykrywanie zerwanych linków i ochrona plików gry.

Mody mogą podmieniać pliki. Przykładowe obszary to `media/Audio/FMODBanks/*.bank`, `media/`, `mediapc/Textures/` oraz osobne mody loaderowe (`dinput8.dll`, ReShade, `.ini`). Nie zakładaj, że instalacja używa `media`: część używa `mediapc`; wykrywaj i ostrzegaj o złym targetcie. Instalacje MS Store/Xbox mogą blokować pliki do czasu włączenia „Zaawansowanych opcji instalacji”.

Modyfikacja plików gry może naruszać regulamin i grozić banem w multiplayerze, Festival Playlist i Eliminatorze. Nie obiecuj, że jakikolwiek mod jest bezpieczny; `online_safe` to deklaracja autora, nie certyfikat. Profil `WANILLA` ma szybko przywracać oryginały przed grą online. Narzędzie nie obsługuje konsol.

## 1. Stack i styl

- Python 3.11+, zero zależności runtime; GUI `tkinter/ttk`, CLI `argparse`.
- `pytest` i `PyInstaller` wyłącznie jako narzędzia deweloperskie.
- Pakowanie docelowe: `FH6AddonLinker.exe` (`--onefile --windowed`).
- Identyfikatory/kod po angielsku; UI, komunikaty, docstringi i dokumentacja po polsku; README ma też sekcję EN.
- Type hints, `dataclasses` w wewnętrznym API, `pathlib` zamiast `os.path`; brak `print()` w logice, używaj loggingu i raportów przekazywanych do UI/CLI.
- Błędy opisują: co się stało → dlaczego → co zrobić. Nie zgaduj faktów o grze. Nieoczywiste decyzje zapisz w `docs/DECISIONS.md` jako ADR (kontekst → decyzja → konsekwencje).
- Brak sieci i telemetrii w v1.0.

## 2. Wymagania funkcjonalne v1.0

### F1 — konfiguracja i wykrywanie gry

GUI ma mieć kreator pierwszego uruchomienia; CLI `set` i `autodetect`. Szukaj instalacji Steam przez `libraryfolders.vdf`, instalacji XboxGames i typowych ścieżek na dyskach. Waliduj obecność `forzahorizon6.exe` lub `media`/`mediapc`. Zła ścieżka ma zwrócić konkretny powód, nie cichy błąd.

### F2 — skan biblioteki

Biblioteka może leżeć w dowolnym katalogu poza grą. Folder jest modem, gdy na tym samym poziomie zawiera `media`, `mediapc` lub `mediaoverride`; w przeciwnym razie skanuj głębiej. Obsłuż `mod.json`, virtual root (zawartość mapowana 1:1 na grę), pomijaj i raportuj pliki poza korzeniami gry. Ignoruj `.DS_Store`, `Thumbs.db`, `desktop.ini`, `__MACOSX` i pliki ukryte. Wykrywaj puste mody, wiele korzeni i niejednoznaczne struktury. Akceptacja: 1000 modów < 3 s; zagnieżdżone mody wykryte; readme nigdy nie trafia do gry.

### F3 — włączanie i wyłączanie

Metody: hardlink (domyślna, ten sam wolumen), symlink (różne wolumeny; Windows może wymagać admina/Trybu dewelopera), copy (awaryjnie, jawnie raportuj duplikowanie danych) i `auto` (hardlink → symlink → copy z wyjaśnieniem błędów). Przed pierwszym zastąpieniem pliku zachowaj oryginał w backupie z SHA-256, rozmiarem i mtime. Nowe pliki nie dostają backupu; zapamiętaj utworzone katalogi. Operacje idempotentne. Akceptacja: hardlink ma `st_nlink >= 2`; disable przywraca bajtowo identyczny oryginał.

### F4 — restore i ochrona

`restore` wyłącza wszystkie mody, przywraca oryginały i usuwa puste katalogi stworzone przez narzędzie. Nigdy nie usuwaj ani nie nadpisuj pliku, którego własności nie można potwierdzić (`samefile`/inode albo hash i rozmiar). Konflikt przenieś do `backups/conflicts/` z logiem, pozostawiając plik gry nienaruszony. Jeżeli gra zaktualizowała lub zastąpiła link, nie przywracaj starego backupu na nowszy plik — oznacz backup jako osierocony i raportuj. Akceptacja: drzewo gry po restore jest identyczne z waniliowym, bez pustych katalogów utworzonych przez narzędzie.

### F5 — status, konflikty i naprawa

Statusy: WŁĄCZONY, CZĘŚCIOWY (n zerwanych), ZERWANY, wyłączony; pokaż liczbę plików i ostrzeżenia. `repair` odtwarza zerwane linki i aktualizuje baseline backupu do nowej waniliowej wersji, gdy plik się zmienił. Dwa mody z tym samym targetem: drugi bez `--force` niczego nie zmienia; `--force` wymaga jawnego ostrzeżenia. Zmiana hasha źródła sugeruje ponowny deploy. `verify` porównuje hashe. Wykrywaj sytuację: gra ma `mediapc/...`, mod celuje w `media/...`, i podpowiadaj przełączenie targetu. Jeśli target nie istnieje, ale identyczna ścieżka istnieje pod drugim korzeniem (`media`/`mediapc`), zablokuj tworzenie równoległego targetu — backup chroni tylko dokładną ścieżkę docelową.

### F6 — profile

`profile save` zapisuje włączone mody; `apply` w jednej operacji włącza brakujące i wyłącza nadmiarowe. `WANILLA` jest wbudowany i nieusuwalny. Import/eksport JSON. GUI ma stale widoczny przycisk „Tryb online (pełna wanilia)” z potwierdzeniem. Mody oznaczone `online_safe: true` mogą pozostać włączone w profilu online, ale UI nadal ostrzega.

### F7 — GUI

`tkinter/ttk`: kreator (folder gry, biblioteka, gotowe); drzewo kategorii/modów z checkboxami, kolumny Wł./Mod/Plików/Stan/Uwagi, filtr, zaznaczanie widocznych i sortowanie. Akcje: zastosuj, wyłącz wszystko, przywróć oryginały, sprawdź, odśwież. Przewijalny/kopiowalny log, postęp i wątki — skan/linkowanie nie blokują UI. Kolory: zielony OK, żółty częściowy, czerwony zerwany, szary wyłączony; pełne ścieżki jako tooltipy. Stały banner ryzyka ToS/banów, About z disclaimerem. Skróty Space, Ctrl+F, F5, Ctrl+Enter. Obsłuż drop ZIP do okna. Pełny cykl ma działać bez CLI; UI nie może zamarzać przy 5000 plików.

### F8 — CLI

Docelowe polecenia (z parytetem funkcji GUI):

```text
fh6linker set --game PATH --library PATH [--backup-dir PATH] [--method auto|hardlink|symlink|copy]
fh6linker autodetect
fh6linker scan [--json]
fh6linker status [--json]
fh6linker enable NAZWA... [--force] [--dry-run]
fh6linker disable NAZWA... [--dry-run]
fh6linker repair [NAZWA...]
fh6linker verify [NAZWA...] [--json]
fh6linker restore --yes
fh6linker profile list|save NAZWA|apply NAZWA|delete NAZWA|export PLIK|import PLIK [--dry-run]
fh6linker import ARCHIWUM.zip [--category KATEGORIA]
fh6linker undo
fh6linker doctor
fh6linker gui
fh6linker --version
```

Kody wyjścia: 0 OK, 1 błąd, 2 konflikt, 3 wymagane podniesienie uprawnień. Każda operacja modyfikująca obsługuje `--dry-run` z pełnym planem.

### F9 — odporność na awarie

Każda operacja ma fazę planu (walidacja, konflikty, miejsce) i wykonanie z journalem write-ahead (`journal.jsonl`: zamiar przed akcją, potwierdzenie po). Stan zapisuj atomowo (`tmp` + `os.replace`) z kopią `.bak`. Blokuj drugą instancję plikiem lock z PID; wygaszaj nieaktualny lock. Operacje blokuj, gdy działa `forzahorizon6.exe`, poza świadomym CLI `--force-while-running`. Po crashu/Ctrl+C kolejny start ma wykryć rozbieżność stanu i journala oraz umożliwić self-heal. Test: przerwanie deployu w połowie 100 plików nie pozostawia stanu niespójnego; `doctor`/`status` wykrywa i naprawia.

### F10 — import archiwów

ZIP przez stdlib `zipfile`, zabezpieczenie zip-slip (`..`), limit rozmiaru i raport zawartości; wykryj `media`/`mediapc` na dowolnym poziomie, użyj nazwy archiwum jako nazwy moda i opcjonalnej kategorii. Bez opcjonalnych `py7zr`/`rarfile` komunikuj czytelnie brak obsługi 7z/RAR.

### F11 — metadane

Opcjonalny `mod.json`: `display_name`, `category`, `author`, `version`, `source_url`, `notes`, `target_prefix`, `online_safe`. GUI umożliwia edycję.

### F12 — logi, undo i doctor

Log operacji `config_dir/logs/ops-YYYY-MM-DD.jsonl`. `undo` cofa ostatnią enable/disable/profile apply z journala. `doctor` raportuje instalację i wersję gry, wolumeny/filesystemy, hardlink/symlink, Tryb dewelopera, admin, wolne miejsce, stan backupów i integralność `state.json`.

## 3. Konfiguracja i stan

Katalog config: `%LOCALAPPDATA%\FH6AddonLinker` na Windowsie, `~/.config/FH6AddonLinker` na Linuksie. `config.json` ma pola `schema`, `game_root`, `library_dir`, `backup_dir`, `method`, `block_while_game_running`, `last_scan`. `state.json` zawiera `schema`, `game_version_seen`, mapę `mods`, `created_dirs` i `orphaned_backups`. Wpis moda zapisuje `source_root`, `moderoot_rel`, `deployed_at`, metodę oraz dla każdego pliku metodę, hash/rozmiar/mtime źródła, ścieżkę backupu i hash wdrożenia. `profiles.json` to mapa nazw profili na listy nazw modów; `WANILLA` mapuje na pustą listę.

## 4. Bezpieczeństwo (nienaruszalne)

- Nigdy nie kasuj pliku, którego własności nie potwierdzono; przed każdym remove wykonaj weryfikację.
- Zawsze zarchiwizuj oryginał przed pierwszym zastąpieniem; restore ma przywracać hash identyczny z oryginałem.
- Działaj wyłącznie w katalogu gry, bibliotece i config; waliduj ścieżki, nie pozwól, by biblioteka leżała w grze ani odwrotnie.
- Wstrzymuj operacje, gdy gra działa. Przed dużą operacją pokaż plan, liczbę plików i rozmiar; sprawdzaj miejsce.
- Nie usuwaj backupów bez jawnego polecenia. Restore/disable nie nadpisuje plików zmienionych przez grę — zapisuje konflikt i raport.
- Brak połączeń sieciowych i telemetrii.

## 5. Docelowa struktura repozytorium

`fh6linker/` zawiera `paths.py`, `linkops.py`, `scanner.py`, `state.py`, `engine.py`, `report.py`, `importer.py`, `cli.py`, `i18n.py` i `gui/{app,wizard,dialogs,theme}.py`. Pozostałe elementy: `README.md`, `LICENSE`, `CHANGELOG.md`, `CONTRIBUTING.md`, `requirements-dev.txt`, `PROMPT.md`, `docs/{USAGE,FAQ,ARCHITECTURE,DECISIONS,RISKS}.md`, testy w `tests/`, skrypty w `scripts/`, packaging w `packaging/` oraz workflow CI/release i szablony zgłoszeń w `.github/`.

## 6. Testy i CI

Obowiązkowe CI: `ubuntu-latest` i `windows-latest`, Python 3.11 i 3.13, `pytest -q`, na Linuksie szybki import GUI przez `xvfb-run`. Fixture docelowo tworzy fałszywą grę (atrapa `forzahorizon6.exe`, `media/Audio/FMODBanks`, `mediapc/Textures`) i bibliotekę z trzema modami.

W kolejnych milestone'ach testuj: deploy hardlinkiem i backup; bajtowy restore oraz sprzątanie katalogów; idempotencję; konflikty; zerwane linki i repair; ochronę obcych plików; profile A→B→A; crash mid-deploy i self-heal; `--dry-run`; ZIP z poprawnym korzeniem, bez korzenia i zip-slip; walidację zagnieżdżenia ścieżek; sugestię `mediapc`. `scripts/demo.sh` będzie smoke testem end-to-end.

## 7. Milestone'y

1. **M0 — szkielet:** katalogi, MIT, README PL+EN, `pyproject.toml`, zależności dev, CI, puste moduły z docstringami, działające `--version`. DoD: testy/CI na obu systemach.
2. **M1 — rdzeń i CLI:** paths, scanner, linkops, state, engine enable/disable/restore, report, CLI, testy rdzenia i `scripts/demo.sh`.
3. **M2 — GUI:** wizard, okno, wątki, log, kolory, banner, skróty; checklist w USAGE i diagnostyka.
4. **M3 — profile/import/metadane/undo/verify:** scenariusze Online i Photo.
5. **M4 — pakowanie:** PyInstaller, ikona, workflow release, portable ZIP.
6. **M5 — utwardzanie:** wydajność, single instance, wykrycie gry, uprawnienia, komplet `doctor`, brak blokowania UI.
7. **M6 — v1.0.0:** FAQ, RISKS, changelog, tag i Release.

Każdy milestone implementuj osobno, pokryj funkcje testami, zaktualizuj changelog, pokaż diff i wyniki, a następnie czekaj na polecenie kontynuacji. Nie dodawaj funkcji spoza tej specyfikacji bez zgody.

## 8. Definition of Done v1.0

Użytkownik bez Pythona pobiera portable ZIP, uruchamia EXE, konfiguruje grę i bibliotekę oraz w 60 sekund włącza pierwszy mod. Zmiana profilu to jedno kliknięcie; WANILLA przywraca oryginały. Restore przechodzi test porównania pełnego drzewa i hashy. Awaria nie zostawia niespójnego stanu; aktualizację gry obsługują status i repair. Zero zależności runtime, sieci i telemetrii. Dokumentacja po polsku z sekcją EN i ostrzeżeniami o ToS/banach. Testy zielone na Windows i Linuksie; portable release zbudowany automatycznie.
