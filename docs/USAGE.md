# Instrukcja użytkownika

## Status

M2 udostępnia GUI desktopowe tkinter/ttk i rdzeń. Do uruchomienia wymaga
Pythona 3.11+ z tkinter. Samodzielny plik Windows `.exe` będzie pakowany w M4.

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
zatwierdzić przed zmianą plików. **Tryb online · przywróć backupy** przywraca
kopie oryginałów dla plików zarządzanych przez aplikację; pliki obce lub
zmienione pozostają nietknięte. W razie potrzeby użyj weryfikacji plików Xbox/Steam.

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
README — również umieszczone wewnątrz korzenia gry moda — są pomijane. Inne pliki
i grafiki dokumentacyjne poza korzeniem gry są raportowane, ale nigdy nie są
wdrażane. Biblioteka i gra powinny znajdować się na tym samym wolumenie, aby
`auto` mogło użyć hardlinków bez dodatkowego miejsca.

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
