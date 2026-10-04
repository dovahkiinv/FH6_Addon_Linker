# Instrukcja użytkownika

## Status

GUI tkinter/ttk i rdzeń są dostępne od M2. Do uruchomienia ze źródeł wymagają
Pythona 3.11+ z tkinter. Repozytorium zawiera już konfigurację pakowania M4:
Windowsowy plik `.exe` buduje się skryptem PowerShell opisanym niżej.

## Uruchomienie GUI

Na Windowsie uruchom `FH6AddonLinker.pyw` dwuklikiem, aby otworzyć okno bez
konsoli. Alternatywnie z katalogu repozytorium:

```powershell
py -3 -m fh6linker gui
```

Przy pierwszym uruchomieniu kreator poprosi o folder gry i bibliotekę modów.
Możesz utworzyć nową bibliotekę bezpośrednio w kreatorze. Użyj przycisku
**Odśwież**, aby przeskanować bibliotekę; zaznacz mody i wybierz
**Zastosuj zaznaczone**. Każda modyfikująca operacja pokazuje plan, który trzeba
zatwierdzić przed zmianą plików. **Tryb online** przywraca kopie oryginałów
plików zarządzanych przez aplikację; pliki obce lub zmienione pozostają
nietknięte. W razie potrzeby użyj weryfikacji plików Xbox/Steam.

## Samodzielny `.exe` dla Windows

Zbuduj plik na Windowsie — PyInstaller nie cross-kompiluje programu Windows
z Linuksa ani macOS. Wymagany jest Python 3.11+ 64-bit. W PowerShellu z katalogu
repozytorium uruchom:

```powershell
py -3 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\scripts\build_exe.ps1
```

Plik `dist\FH6AddonLinker.exe` jest pojedynczym programem GUI z Pythonem i
Tkinterem w środku; na komputerze docelowym nie trzeba instalować Pythona.
Konfiguracja i kopie zapasowe są przechowywane w profilu użytkownika, poza
folderem EXE. Budowanie można też uruchomić przez **Actions → Windows
executable → Run workflow**; z Actions pobierz artefakt
`FH6AddonLinker-windows-x64`.

EXE nie jest podpisany certyfikatem code-signing, więc SmartScreen może pokazać
ostrzeżenie przy pierwszym uruchomieniu.

## Co robi kopia oryginału

To nie jest kopia całej instalacji gry. Przed podmianą aplikacja kopiuje plik,
który już istnieje dokładnie pod targetem moda, np. `media/Audio/example.bank`,
do osobnego magazynu kopii. Przy wyłączeniu usuwa własny link i przywraca tę
kopię. Nowy target nie ma oryginału do zapisania — przywracanie usuwa go, o ile
nadal należy do aplikacji.

`media/...` i `mediapc/...` są różnymi ścieżkami. Jeżeli target moda nie istnieje,
ale ten sam plik jest w drugim drzewie, wdrożenie zostanie zatrzymane zamiast
tworzyć równoległą ścieżkę. Popraw wtedy korzeń w strukturze moda i odśwież
bibliotekę. Gdy pliki istnieją w obu drzewach, plan jasno ostrzega, że kopia
obejmie wyłącznie dokładnie wybrany target.

## CLI pomocnicze

Polecenia tekstowe przydają się do diagnostyki lub automatyzacji, ale nie są
wymagane do zwykłego używania GUI. Instalacja developerska i testy:

```console
python -m pip install -e .
python -m fh6linker --version
```

## Przygotowanie biblioteki

Biblioteka ma leżeć poza folderem gry. Zwykły folder moda powinien zawierać
dokładnie jeden katalog `media`, `mediapc` albo `mediaoverride`:

```text
D:\FH6Mods\
  Audio\
    Engine Mod\
      mod.json                 (opcjonalnie)
      readme.txt               (pomijany)
      media\
        Audio\FMODBanks\engine.bank
```

Mody bez katalogu `media` mogą być virtual-root, jeśli ich folder zawiera
`mod.json`; pozostałe pliki mapują się wtedy bezpośrednio od katalogu głównego
gry. `mod.json` nie jest wdrażany. Przykład:

```text
D:\FH6Mods\
  Narzędzia\
    ReShade\
      mod.json
      dinput8.dll
      reshade.ini
      README.md                (pomijany)
```

Wszystko pod katalogiem `media` trafi do takiej samej ścieżki w grze. Pliki
README — również umieszczone wewnątrz korzenia gry moda — są pomijane. Archiwa
pozostawione w bibliotece są cicho ignorowane i nie są wdrażane; przed użyciem
moda rozpakuj jego zawartość do folderu moda. Inne pliki i grafiki dokumentacyjne
poza korzeniem gry są raportowane, ale nigdy nie są wdrażane. Biblioteka i gra
powinny znajdować się na tym samym wolumenie, aby `auto` mogło użyć hardlinków
bez dodatkowego miejsca.

## Bezpieczny przebieg

Najpierw wskaż istniejące foldery gry i biblioteki:

```console
fh6linker autodetect
fh6linker set --game "C:\Games\ForzaHorizon6" --library "D:\FH6Mods" --method auto
fh6linker scan
```

Sprawdź plan przed modyfikacją:

```console
fh6linker enable "Engine Mod" --dry-run
```

Jeśli plan jest poprawny, włącz moda, sprawdź status, a potem go wyłącz:

```console
fh6linker enable "Engine Mod"
fh6linker status
fh6linker verify "Engine Mod"
fh6linker disable "Engine Mod"
```

Aby wyłączyć wszystkie zarządzane mody i przywrócić dostępne backupy:

```console
fh6linker restore --yes
```

`restore` wymaga jawnego `--yes`. Obce lub zmienione pliki pozostają bez zmian;
w razie potrzeby zweryfikuj integralność gry w Xbox/Steam. Gdy gra działa,
operacje modyfikujące są blokowane; zamknij FH6 przed wdrożeniem lub
przywracaniem plików.

## Demo bez prawdziwej gry

Z katalogu repozytorium uruchom `bash scripts/demo.sh` na Linuksie albo
`powershell -ExecutionPolicy Bypass -File scripts/demo.ps1` na Windowsie. Demo
buduje tymczasową atrapę gry, wykonuje pełny cykl i usuwa katalog tymczasowy.

## Ważne

- Nie używaj modów podmieniających pliki podczas gry online. Mogą naruszać
  regulamin i grozić banem.
- `--force` służy wyłącznie do jawnego przejęcia pliku wdrożonego przez inny
  mod. Nie pozwala nadpisać pliku, którego własności nie da się potwierdzić.
- Gdy aktualizacja gry zastąpi link, `status` powinien pokazać zerwanie; użyj
  `repair` po sprawdzeniu, że aktualny plik gry ma zostać nową kopią bazową.
- GUI i kreator są dostępne od M2; samodzielny `.exe` pojawi się w M4.
