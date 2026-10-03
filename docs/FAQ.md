# FAQ

## Czy mogę już używać GUI?

Tak. GUI tkinter/ttk jest dostępne od M2. Na Windowsie uruchom
`FH6AddonLinker.pyw` dwuklikiem albo wpisz `py -3.11 -m fh6linker gui`.
Samodzielny portable `.exe` jest planowany na M4.

## Czy muszę używać CLI?

Nie. Zwykłe zarządzanie modami odbywa się w GUI. Przed zatwierdzeniem każdej
zmiany okno pokazuje plan; przed wdrożeniem zamknij grę. Modyfikowanie plików
może naruszać regulamin i skutkować banem. Nie testuj modów online.

## Co dzieje się z oryginalnymi plikami gry?

Przed zastąpieniem pliku silnik kopiuje go do magazynu backupów i sprawdza hash.
`disable` lub `restore --yes` usuwa tylko potwierdzony link, a następnie
przywraca backup. Plik obcy lub zmieniony pozostaje bez zmian, a backupy nie są
automatycznie kasowane. `restore` nie zastępuje weryfikacji plików w Xbox/Steam.

## Czy mogę zmienić foldery, gdy mody są wdrożone?

Nie. Kreator blokuje zmianę folderu gry, biblioteki lub backupów, jeśli w stanie
aplikacji są wdrożone pliki. Najpierw przywróć zarządzane backupy, a potem zmień
ścieżki. Zmiana samej metody linkowania dotyczy kolejnych wdrożeń.

## Co jeśli gra zaktualizuje plik?

`status` wykrywa zerwany link. `disable` nie nadpisuje obcego/nowszego pliku;
zgłasza konflikt. `repair` zachowuje aktualny plik gry jako nową kopię bazową,
a następnie odtwarza link.

## Co zrobić, jeśli pliki gry są zablokowane?

Wersja MS Store może wymagać włączenia „Zaawansowanych opcji instalacji” w
aplikacji Xbox. Diagnostyka uprawnień będzie rozwijana w kolejnych etapach.

## Dlaczego istnieją katalogi `media` i `mediapc`?

Niektóre instalacje lub mody używają różnych korzeni. Zły katalog docelowy może
sprawić, że mod nie zadziała bez komunikatu gry. Narzędzie ostrzega, jeśli
odpowiednik pliku istnieje pod drugim korzeniem.
