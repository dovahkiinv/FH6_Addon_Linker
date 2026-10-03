# FAQ

## Czy mogę już uruchomić GUI albo `.exe`?

Nie. Aktualny etap M1 udostępnia rdzeń i CLI. GUI tkinter powstanie w M2, a
portable `.exe` w M4.

## Czy mogę już włączyć moda z CLI?

Tak, ale najpierw użyj `fh6linker enable NAZWA --dry-run`, sprawdź plan i upewnij
się, że gra jest zamknięta. Modyfikowanie plików może naruszać regulamin i
skutkować banem. Nie testuj modów online.

## Co dzieje się z oryginalnymi plikami gry?

Przed zastąpieniem pliku silnik kopiuje go do magazynu backupów i sprawdza hash.
`disable` lub `restore --yes` usuwa tylko potwierdzony link, a następnie
przywraca backup. Backupy nie są automatycznie kasowane.

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
