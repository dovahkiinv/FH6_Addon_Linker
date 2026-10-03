# Ryzyka i ostrzeżenia

> **Modyfikowanie plików gry odbywa się na własną odpowiedzialność.** FH6 Addon
> Linker nie jest powiązany z Playground Games, Xbox ani Microsoft i nie może
> zagwarantować braku bana, utraty plików lub problemów po aktualizacji gry.

## Regulamin i bany

Zgodnie z wymaganiami projektu oficjalne FAQ FH6 nie zezwala na modyfikowanie
plików gry. Mody zastępujące pliki w `media` lub `mediapc` mogą skutkować banem
w multiplayerze, Festival Playlist lub Eliminatorze. Oznaczenie `online_safe`
nie jest certyfikatem ani gwarancją bezpieczeństwa. Przed grą online należy
przywrócić pełną wanilię; docelowo służy do tego profil `WANILLA`.

## Integralność i aktualizacje

Weryfikacja integralności lub anty-cheat może wykryć zmienione pliki i linki.
Aktualizacja gry może nadpisać wdrożony plik, zerwać link albo sprawić, że
zapisana kopia nie odpowiada już bieżącej wersji. Narzędzie ma wykrywać takie
sytuacje, nie nadpisywać obcych plików i raportować konflikty. Do czasu
implementacji tych zabezpieczeń nie należy używać go do modyfikowania gry.

## Microsoft Store i ścieżki

Instalacja MS Store/Xbox może blokować zapis do plików gry, dopóki użytkownik
nie włączy „Zaawansowanych opcji instalacji” w aplikacji Xbox. Instalacje mogą
też używać `mediapc` zamiast `media`; błędny katalog docelowy może spowodować,
że mod nie zadziała bez komunikatu.

## Zakres wsparcia

Projekt jest przeznaczony dla instalacji PC z Windows 10/11 i ma działać także
na Linuksie/SteamOS. Nie obejmuje konsol ani modów wymagających własnych
instalatorów zapisujących dane poza katalogiem gry. M0 nie obsługuje jeszcze
żadnej instalacji.

## Prywatność

Założeniem wersji 1.0 jest brak telemetrii i połączeń sieciowych. W M0 nie ma
jeszcze funkcji aplikacyjnych, które mogłyby skanować grę lub bibliotekę.
