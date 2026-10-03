# FAQ

## Czy ta wersja może włączyć moda?

Nie. M0 zawiera tylko szkielet pakietu i polecenie wersji; skanowanie i
linkowanie nie są zaimplementowane.

## Czy modyfikacje plików gry są bezpieczne w trybie online?

Nie można tego zagwarantować. Modyfikowanie plików może naruszać regulamin i
skutkować banem. Przed użyciem trybów online należy przywrócić waniliowe pliki.
Szczegóły: [RISKS.md](RISKS.md).

## Co zrobić, jeśli pliki gry są zablokowane?

Wersja MS Store może wymagać włączenia „Zaawansowanych opcji instalacji” w
aplikacji Xbox. Obsługa i diagnostyka tej sytuacji są planowane na kolejne
milestone'y.

## Dlaczego istnieją katalogi `media` i `mediapc`?

Niektóre instalacje lub mody używają różnych korzeni. Zły target może sprawić,
że mod nie zadziała bez komunikatu gry. Docelowo narzędzie ma wykrywać i
ostrzegać o tej różnicy.
