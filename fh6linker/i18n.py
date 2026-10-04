"""Proste tłumaczenia interfejsu oraz zapis wybranego języka GUI."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "pl"
SUPPORTED_LANGUAGES = ("pl", "en")
LANGUAGE_LABELS = {"pl": "Polski", "en": "English"}

# Stałe etykiety GUI. Treść raportów i komunikaty silnika pozostają w języku
# polskim, natomiast wszystkie kontrolki aplikacji można przełączyć na angielski.
_STRINGS: dict[str, dict[str, str]] = {
    "menu_application": {"pl": "Aplikacja", "en": "Application"},
    "menu_setup": {"pl": "Konfiguruj foldery…", "en": "Configure folders…"},
    "menu_close": {"pl": "Zamknij", "en": "Exit"},
    "menu_help": {"pl": "Pomoc", "en": "Help"},
    "menu_guide": {"pl": "Instrukcja / samouczek…", "en": "User guide / tutorial…"},
    "menu_about": {"pl": "O aplikacji i ryzyku…", "en": "About and safety…"},
    "window_title": {"pl": "FH6 Addon Linker", "en": "FH6 Addon Linker"},
    "header_subtitle": {
        "pl": "Biblioteka modów · bezpieczne wdrażanie i przywracanie",
        "en": "Mod library · reversible deployment and restore",
    },
    "local_badge": {"pl": "LOKALNIE · OFFLINE", "en": "LOCAL · OFFLINE"},
    "setup_button": {"pl": "Ustawienia", "en": "Settings"},
    "safety_banner": {
        "pl": (
            "⚠ Modyfikowanie plików FH6 może naruszać regulamin i grozić banem. "
            "Przed grą online przywróć oryginały i zweryfikuj pliki w Xbox/Steam; "
            "aplikacja nie gwarantuje bezpieczeństwa konta."
        ),
        "en": (
            "⚠ Modifying FH6 files may violate the terms of service and result in a ban. "
            "Restore originals and verify files in Xbox/Steam before playing online; "
            "the app cannot guarantee account safety."
        ),
    },
    "path_game": {"pl": "FOLDER GRY", "en": "GAME FOLDER"},
    "path_library": {"pl": "BIBLIOTEKA MODÓW", "en": "MOD LIBRARY"},
    "path_backups": {"pl": "KOPIE ORYGINAŁÓW", "en": "ORIGINAL BACKUPS"},
    "open_folder": {"pl": "Otwórz folder", "en": "Open folder"},
    "folder_missing_title": {"pl": "Folder nie istnieje", "en": "Folder not found"},
    "folder_missing_body": {
        "pl": "Nie znaleziono folderu:\n{path}",
        "en": "The folder could not be found:\n{path}",
    },
    "backup_create_title": {"pl": "Utworzyć folder kopii?", "en": "Create backup folder?"},
    "backup_create_body": {
        "pl": "Folder kopii jeszcze nie istnieje:\n{path}\n\nUtworzyć pusty folder? Żadna kopia nie powstanie, dopóki aplikacja nie zastąpi istniejącego pliku.",
        "en": "The backup folder does not exist yet:\n{path}\n\nCreate an empty folder? No backup will be made unless the app replaces an existing file.",
    },
    "folder_open_error_title": {"pl": "Nie można otworzyć folderu", "en": "Could not open folder"},
    "folder_open_error_body": {"pl": "Nie udało się otworzyć:\n{path}\n\n{error}", "en": "Could not open:\n{path}\n\n{error}"},
    "metric_library": {"pl": "W BIBLIOTECE", "en": "IN LIBRARY"},
    "metric_active": {"pl": "AKTYWNE", "en": "ACTIVE"},
    "metric_attention": {"pl": "WYMAGAJĄ UWAGI", "en": "NEED ATTENTION"},
    "action_enable_all": {"pl": "Włącz wszystkie", "en": "Enable all"},
    "action_apply_selected": {"pl": "Zastosuj wybrane", "en": "Apply selected"},
    "action_disable_all": {"pl": "Wyłącz wszystkie", "en": "Disable all"},
    "action_restore": {"pl": "Przywróć oryginały", "en": "Restore originals"},
    "action_online": {"pl": "Tryb online", "en": "Online mode"},
    "action_verify": {"pl": "Sprawdź", "en": "Verify"},
    "action_repair": {"pl": "Napraw", "en": "Repair"},
    "action_refresh": {"pl": "Odśwież", "en": "Refresh"},
    "search_mods": {"pl": "Szukaj moda", "en": "Search mods"},
    "select_visible": {"pl": "Zaznacz widoczne", "en": "Select visible"},
    "deselect_visible": {"pl": "Odznacz widoczne", "en": "Deselect visible"},
    "clear_selection": {"pl": "Wyczyść wybór", "en": "Clear selection"},
    "select_all": {"pl": "Zaznacz wszystkie", "en": "Select all"},
    "deselect_all": {"pl": "Odznacz wszystkie", "en": "Deselect all"},
    "category_uncategorized": {"pl": "Bez kategorii", "en": "Uncategorized"},
    "category_not_in_library": {"pl": "Brak w bibliotece", "en": "Not in library"},
    "category_camera": {"pl": "Kamera", "en": "Camera"},
    "category_interface": {"pl": "Interfejs", "en": "Interface"},
    "category_graphics": {"pl": "Grafika", "en": "Graphics"},
    "category_map": {"pl": "Mapa", "en": "Map"},
    "guide_title": {"pl": "Instrukcja / samouczek", "en": "User guide / tutorial"},
    "guide_intro": {
        "pl": "FH6 Addon Linker wykrywa rozpakowane mody i pomaga wdrażać je w sposób odwracalny. Przed zmianą plików gry zawsze pokazuje plan.",
        "en": "FH6 Addon Linker detects unpacked mods and helps deploy them reversibly. It always shows a plan before changing game files.",
    },
    "guide_setup": {
        "pl": "1. Foldery — w menu Aplikacja → Konfiguruj foldery wskaż folder gry, bibliotekę modów (poza folderem gry) i magazyn kopii.",
        "en": "1. Folders — open Application → Configure folders and choose the game folder, a mod library (outside the game folder), and a backup location.",
    },
    "guide_library": {
        "pl": "2. Biblioteka — umieść każdy już rozpakowany mod we własnym folderze. Foldery kategorii, np. Audio/Radio, grupują mody. Nie przenoś wdrożonego moda bez wcześniejszego wyłączenia — zmienia to jego ID. Archiwa .zip, .rar, .7z i .7zip są cicho ignorowane; aplikacja ich nie rozpakowuje.",
        "en": "2. Library — put each already-extracted mod in its own folder. Category folders such as Audio/Radio group mods. Disable a deployed mod before moving its folder; moving it changes its ID. .zip, .rar, .7z, and .7zip archives are silently ignored and are never extracted by the app.",
    },
    "guide_scan": {
        "pl": "3. Skan — kliknij Odśwież. Kategorie mogą pochodzić z folderu nadrzędnego, mod.json albo ostrożnego rozpoznania zawartości. Niepewne mody pozostają Bez kategorii.",
        "en": "3. Scan — click Refresh. Categories can come from the parent folder, mod.json, or conservative content hints. Uncertain mods remain Uncategorized.",
    },
    "guide_selection": {
        "pl": "4. Wybór — Zaznacz wszystkie zaznacza prawidłowe wykryte mody, Odznacz wszystkie czyści wybór. Zaznacz widoczne i Wyczyść wybór działają na aktualny filtr. To tylko wybór checkboxów, nie to samo co Włącz wszystkie; pliki gry zmienia dopiero Zastosuj wybrane po zatwierdzeniu planu.",
        "en": "4. Selection — Select all checks valid detected mods; Deselect all clears the checkboxes. Select visible and Clear selection affect the current filter. This only changes selection, not game files, and is different from Enable all. Apply selected changes files only after you approve its plan.",
    },
    "guide_apply": {
        "pl": "5. Plan — kliknij Zastosuj wybrane (albo Włącz wszystkie / Wyłącz wszystkie). Sprawdź źródła, dokładne cele, konflikty i ostrzeżenia, a następnie zatwierdź plan. Anulowanie pozostawia pliki gry bez zmian.",
        "en": "5. Plan — click Apply selected (or Enable all / Disable all). Review source files, exact targets, conflicts, and warnings, then approve the plan. Cancelling leaves game files unchanged.",
    },
    "guide_backups": {
        "pl": "Kopie — backup powstaje tylko przy zastąpieniu istniejącego pliku pod dokładnym targetem. Nowe ścieżki nie mają kopii; przy wyłączeniu aplikacja usuwa własne nowe pliki.",
        "en": "Backups — a backup is made only when replacing an existing file at the exact target. New paths have no backup; disabling the mod removes app-managed new files.",
    },
    "guide_restore": {
        "pl": "6. Przywracanie — Wyłącz wszystkie usuwa wdrożone mody, a Przywróć oryginały / Tryb online przywraca dostępne kopie bazowe. Zamknij grę przed operacją.",
        "en": "6. Restore — Disable all removes deployed mods; Restore originals / Online mode restores available baseline backups. Close the game before running an operation.",
    },
    "guide_safety": {
        "pl": "Ostrzeżenie — modyfikowanie plików może naruszać regulamin gry online i grozić banem. Przed grą online przywróć oryginały i zweryfikuj pliki w Xbox/Steam.",
        "en": "Safety — modifying files may violate online-game terms and result in a ban. Restore originals and verify files in Xbox/Steam before playing online.",
    },
    "guide_close": {"pl": "Zamknij", "en": "Close"},
    "tree_mod": {"pl": "Mod / kategoria", "en": "Mod / category"},
    "tree_choice": {"pl": "Wybór", "en": "Selected"},
    "tree_active": {"pl": "Aktywny", "en": "Active"},
    "tree_files": {"pl": "Pliki", "en": "Files"},
    "tree_status": {"pl": "Stan", "en": "Status"},
    "tree_notes": {"pl": "Uwagi", "en": "Notes"},
    "empty_filter": {
        "pl": "Brak wyników dla filtra „{query}”.\nWyczyść filtr, aby zobaczyć wszystkie mody.",
        "en": "No results for “{query}”.\nClear the filter to see all mods.",
    },
    "empty_library": {
        "pl": "Nie znaleziono modów w bibliotece.\nMod powinien zawierać media, mediapc, mediaoverride, mod.json albo rozpoznawalny układ FH6 Universal Radio.\nSprawdź ścieżkę biblioteki i kliknij „Odśwież”.",
        "en": "No mods found in the library.\nA mod should contain media, mediapc, mediaoverride, mod.json, or the recognized FH6 Universal Radio layout.\nCheck the library path and click “Refresh”.",
    },
    "log_header": {"pl": "Dziennik operacji", "en": "Operation log"},
    "copy_log": {"pl": "Kopiuj log", "en": "Copy log"},
    "status_ready": {"pl": "Gotowe", "en": "Ready"},
    "status_loading": {"pl": "Wczytywanie…", "en": "Loading…"},
    "status_scanning": {"pl": "Skanuję bibliotekę i sprawdzam wdrożenia…", "en": "Scanning the library and checking deployments…"},
    "status_config_missing": {"pl": "Nie skonfigurowano folderów", "en": "Folders are not configured"},
    "path_not_configured": {"pl": "Nie skonfigurowano", "en": "Not configured"},
    "path_read_error": {"pl": "Nie można odczytać konfiguracji: {error}", "en": "Could not read configuration: {error}"},
    "log_startup": {
        "pl": "Uruchomiono FH6 Addon Linker. Najpierw sprawdź plan przed wdrożeniem.",
        "en": "FH6 Addon Linker started. Review the plan before deployment.",
    },
    "log_config_saved": {"pl": "Zapisano konfigurację folderów.", "en": "Folder configuration saved."},
    "log_config_required": {"pl": "Konfiguracja wymaga uzupełnienia: {error}", "en": "Configuration needs attention: {error}"},
    "log_scan_summary": {
        "pl": "Odświeżono bibliotekę: {mods} modów, {active} aktywnych lub wymagających uwagi.",
        "en": "Library refreshed: {mods} mods, {active} active or needing attention.",
    },
    "status_scan_errors": {"pl": "Skan zakończony z {count} błędami", "en": "Scan finished with {count} error(s)"},
    "status_status_errors": {"pl": "Odczyt statusu zakończony z błędami", "en": "Status check finished with errors"},
    "status_found_mods": {"pl": "Gotowe · wykryto {count} modów", "en": "Ready · found {count} mods"},
    "state_enabled": {"pl": "WŁĄCZONY", "en": "ENABLED"},
    "state_partial": {"pl": "CZĘŚCIOWY", "en": "PARTIAL"},
    "state_broken": {"pl": "ZERWANY", "en": "BROKEN"},
    "state_disabled": {"pl": "wyłączony", "en": "Disabled"},
    "selection_no_change": {"pl": "Wybór nie wymaga zmian.", "en": "The selection does not require any changes."},
    "enable_all_title": {"pl": "Włącz wszystkie mody", "en": "Enable all mods"},
    "enable_all_none_title": {"pl": "Brak modów do włączenia", "en": "No mods to enable"},
    "enable_all_none_body": {"pl": "Nie znaleziono prawidłowych, wyłączonych modów w bibliotece.", "en": "No valid disabled mods were found in the library."},
    "enable_all_done_body": {"pl": "Wszystkie prawidłowe mody z biblioteki są już aktywne.", "en": "All valid mods in the library are already active."},
    "disable_none_title": {"pl": "Brak aktywnych modów", "en": "No active mods"},
    "disable_none_body": {"pl": "Nie ma modów do wyłączenia.", "en": "There are no mods to disable."},
    "disable_all_title": {"pl": "Wyłącz wszystkie mody", "en": "Disable all mods"},
    "restore_title": {"pl": "Przywróć oryginalne pliki gry", "en": "Restore original game files"},
    "online_title": {"pl": "Tryb online — przywróć oryginały", "en": "Online mode — restore originals"},
    "online_body": {
        "pl": "Ta operacja wyłączy zarządzane mody i przywróci zapisane kopie oryginałów.\n\nPliki obce lub zmienione pozostaną nietknięte; w razie potrzeby użyj weryfikacji plików w Xbox/Steam.\n\nModyfikowanie plików może naruszać regulamin i grozić banem; przywrócenie nie gwarantuje bezpieczeństwa konta.\n\nCzy przygotować plan przywrócenia?",
        "en": "This will disable managed mods and restore saved original-file backups.\n\nForeign or changed files will be left untouched; use Xbox/Steam file verification if needed.\n\nModifying game files may violate the terms of service and result in a ban; restoring files cannot guarantee account safety.\n\nPrepare a restore plan?",
    },
    "no_mods_title": {"pl": "Brak modów", "en": "No mods"},
    "verify_none_body": {"pl": "Nie ma wdrożonych modów do sprawdzenia.", "en": "There are no deployed mods to verify."},
    "verify_progress": {"pl": "Weryfikuję pliki…", "en": "Verifying files…"},
    "repair_none_title": {"pl": "Nie znaleziono zerwanych linków", "en": "No broken links found"},
    "repair_none_body": {"pl": "Zaznacz wdrożone mody albo użyj przycisku Odśwież.", "en": "Select deployed mods or use the Refresh button."},
    "repair_title": {"pl": "Napraw zaznaczone mody", "en": "Repair selected mods"},
    "task_plan": {"pl": "Sprawdzam pliki i przygotowuję plan…", "en": "Checking files and preparing a plan…"},
    "task_execute": {"pl": "Wykonuję zatwierdzone zmiany…", "en": "Applying approved changes…"},
    "log_no_changes": {"pl": "Nie ma zmian do wykonania.", "en": "There are no changes to perform."},
    "log_plan_cancelled": {"pl": "Anulowano plan; pliki gry pozostały bez zmian.", "en": "Plan cancelled; game files were not changed."},
    "operation_error_title": {"pl": "Operacja wymaga uwagi", "en": "Operation needs attention"},
    "conflicts_title": {"pl": "Pozostawiono konflikty", "en": "Conflicts were left untouched"},
    "conflicts_body": {
        "pl": "Niektóre pliki nie należą do narzędzia i pozostały bez zmian:\n\n{conflicts}",
        "en": "Some files are not managed by this tool and were left untouched:\n\n{conflicts}",
    },
    "report_summary": {
        "pl": "{operation}: {changed} zmian, {planned} plików w planie (kod {code}).",
        "en": "{operation}: {changed} change(s), {planned} file(s) planned (code {code}).",
    },
    "report_warning": {"pl": "UWAGA: {message}", "en": "WARNING: {message}"},
    "report_conflict": {"pl": "KONFLIKT: {message}", "en": "CONFLICT: {message}"},
    "report_error": {"pl": "BŁĄD: {message}", "en": "ERROR: {message}"},
    "report_privilege": {
        "pl": "Wymagane są uprawnienia administratora lub Tryb dewelopera Windows.",
        "en": "Administrator privileges or Windows Developer Mode are required.",
    },
    "task_failed_status": {"pl": "Operacja zakończona błędem", "en": "Operation failed"},
    "task_failed_title": {"pl": "Operacja nie powiodła się", "en": "Operation failed"},
    "busy_title": {"pl": "Operacja w toku", "en": "Operation in progress"},
    "busy_setup_body": {
        "pl": "Poczekaj na zakończenie bieżącej operacji przed zmianą ścieżek.",
        "en": "Wait for the current operation to finish before changing paths.",
    },
    "busy_close_body": {
        "pl": "Poczekaj, aż bieżąca operacja zakończy się przed zamknięciem aplikacji.",
        "en": "Wait for the current operation to finish before closing the app.",
    },
    "status_details": {"pl": "Stan", "en": "Status"},
    "details_id": {"pl": "ID", "en": "ID"},
    "details_category": {"pl": "Kategoria", "en": "Category"},
    "details_files": {"pl": "Pliki", "en": "Files"},
    "details_broken": {"pl": "zerwane", "en": "broken"},
    "details_source": {"pl": "Źródło", "en": "Source"},
    "details_targets": {"pl": "Targety", "en": "Targets"},
    "details_notes": {"pl": "Uwagi", "en": "Notes"},
    "details_none": {"pl": "Brak", "en": "None"},
    "details_no_warnings": {"pl": "Brak ostrzeżeń.", "en": "No warnings."},
    "details_more_files": {"pl": "… i {count} kolejnych plików", "en": "… and {count} more file(s)"},
    "details_more_paths": {"pl": "… i {count} kolejnych ścieżek", "en": "… and {count} more path(s)"},
    "about_title": {"pl": "O aplikacji", "en": "About"},
    "about_body": {
        "pl": "FH6 Addon Linker {version}\n\nNarzędzie społecznościowe, niezwiązane z Playground Games, Xbox ani Microsoft.\n\nModyfikowanie plików gry może naruszać regulamin i grozić banem. Aplikacja nie gwarantuje bezpieczeństwa konta ani modów.",
        "en": "FH6 Addon Linker {version}\n\nA community tool, not affiliated with Playground Games, Xbox, or Microsoft.\n\nModifying game files may violate the terms of service and result in a ban. The app cannot guarantee account or mod safety.",
    },
    "wizard_title": {"pl": "Konfiguracja FH6 Addon Linker", "en": "FH6 Addon Linker setup"},
    "wizard_heading": {"pl": "Przygotuj bibliotekę modów", "en": "Set up your mod library"},
    "wizard_intro": {
        "pl": "Wskaż folder instalacji FH6 i osobny katalog biblioteki. Przed podmianą aplikacja kopiuje oryginał pliku z dokładnej ścieżki docelowej.",
        "en": "Choose the FH6 installation folder and a separate mod-library folder. Before replacing a file, the app backs up the original at that exact target path.",
    },
    "wizard_game": {"pl": "Folder gry", "en": "Game folder"},
    "wizard_library": {"pl": "Biblioteka modów", "en": "Mod library"},
    "wizard_backup": {"pl": "Folder kopii oryginałów", "en": "Original backups folder"},
    "wizard_browse": {"pl": "Przeglądaj…", "en": "Browse…"},
    "wizard_backup_note": {
        "pl": "Kopia obejmuje wyłącznie istniejący plik pod dokładną ścieżką moda — nie całą grę ani odpowiednik media/mediapc. Gdy odpowiednik jest tylko pod drugim korzeniem, plan ostrzeże, ale pozwoli zatwierdzić target moda. Nowe pliki są usuwane przy przywracaniu, jeśli nadal należą do aplikacji. Puste pole użyje domyślnego katalogu aplikacji.",
        "en": "Backups include only an existing file at the exact mod target—not the whole game or a matching file under media/mediapc's other root. If a counterpart exists only under the other root, the plan warns you but still lets you approve the mod's target. Newly added files are removed during restore if they are still managed by the app. Leave blank to use the app's default folder.",
    },
    "wizard_method": {"pl": "Metoda linkowania", "en": "Linking method"},
    "wizard_method_help": {"pl": "auto: hardlink → symlink → kopia", "en": "auto: hard link → symlink → copy"},
    "wizard_detect": {"pl": "Wykryj instalacje gry", "en": "Detect game installations"},
    "wizard_warning": {
        "pl": "Ważne: biblioteka nie może znajdować się wewnątrz folderu gry. Przed wdrażaniem modów zamknij FH6. Mody mogą naruszać regulamin i grozić banem.",
        "en": "Important: the mod library must be outside the game folder. Close FH6 before deploying mods. Mods may violate the terms of service and result in a ban.",
    },
    "wizard_cancel": {"pl": "Anuluj", "en": "Cancel"},
    "wizard_save": {"pl": "Zapisz konfigurację", "en": "Save configuration"},
    "wizard_no_paths_title": {"pl": "Brak ścieżki", "en": "Missing path"},
    "wizard_no_paths_body": {"pl": "Wskaż folder gry i bibliotekę modów.", "en": "Choose the game folder and mod library."},
    "wizard_state_error_title": {"pl": "Nie można sprawdzić wdrożeń", "en": "Could not check deployments"},
    "wizard_state_error_body": {
        "pl": "Nie odczytano state.json: {error}\n\nKonfiguracji nie zapisano, aby nie utracić możliwości przywrócenia plików.",
        "en": "Could not read state.json: {error}\n\nConfiguration was not saved so file restoration remains possible.",
    },
    "wizard_active_title": {"pl": "Najpierw przywróć wdrożone pliki", "en": "Restore deployed files first"},
    "wizard_active_body": {
        "pl": "Nie zmieniono folderu gry, biblioteki ani backupów, ponieważ istnieją pliki wdrożone ({mods}). Użyj najpierw przycisku „Przywróć oryginały” i ponów konfigurację.",
        "en": "The game, library, or backup paths were not changed because deployed files exist ({mods}). Use “Restore originals” first, then configure again.",
    },
    "wizard_create_library_title": {"pl": "Utworzyć bibliotekę?", "en": "Create mod library?"},
    "wizard_create_library_body": {"pl": "Folder nie istnieje:\n{path}\n\nUtworzyć go teraz?", "en": "This folder does not exist:\n{path}\n\nCreate it now?"},
    "wizard_create_library_error": {"pl": "Nie można utworzyć biblioteki", "en": "Could not create library"},
    "wizard_config_error_title": {"pl": "Nie zapisano konfiguracji", "en": "Configuration was not saved"},
    "wizard_config_error_body": {"pl": "{error}\n\nSprawdź ścieżki i spróbuj ponownie.", "en": "{error}\n\nCheck the paths and try again."},
    "wizard_detect_none_title": {"pl": "Nie wykryto gry", "en": "No game installation found"},
    "wizard_detect_none_body": {"pl": "Nie znaleziono instalacji FH6. Wskaż folder ręcznie przyciskiem Przeglądaj.", "en": "No FH6 installation was found. Choose the folder manually with Browse."},
    "wizard_detect_multiple_title": {"pl": "Wykryto kilka instalacji", "en": "Multiple installations found"},
    "wizard_detect_multiple_body": {"pl": "Wybrano pierwszą z listy. Możesz wskazać inną w polu obok przycisku.", "en": "The first installation was selected. Choose another one in the field beside the button if needed."},
    "wizard_game_picker": {"pl": "Wybierz folder instalacji Forza Horizon 6", "en": "Choose the Forza Horizon 6 installation folder"},
    "wizard_library_picker": {"pl": "Wybierz bibliotekę modów", "en": "Choose the mod library"},
    "wizard_backup_picker": {"pl": "Wybierz katalog backupów", "en": "Choose the backups folder"},
    "wizard_validation_error": {"pl": "Nie można utworzyć biblioteki", "en": "Could not create library"},
    "language_save_error": {"pl": "Nie udało się zapisać języka interfejsu: {error}", "en": "Could not save the interface language: {error}"},
    "path_summary": {"pl": "Gra: {game} · Biblioteka: {library} · Kopie: {backups}", "en": "Game: {game} · Library: {library} · Backups: {backups}"},
    "folder_kind_game": {"pl": "folderu gry", "en": "game folder"},
    "folder_kind_library": {"pl": "biblioteki modów", "en": "mod library"},
    "folder_kind_backup": {"pl": "folderu kopii oryginałów", "en": "original backups folder"},
    "folder_not_configured_body": {"pl": "Nie skonfigurowano {folder}.", "en": "The {folder} has not been configured."},
    "value_yes": {"pl": "Tak", "en": "Yes"},
    "value_no": {"pl": "Nie", "en": "No"},
    "task_failed_log": {"pl": "BŁĄD ({label}): {error}", "en": "ERROR ({label}): {error}"},
}


_STRINGS.update(
    {
        "plan_summary": {"pl": "Plan obejmuje {count} zmian w plikach.", "en": "Plan includes {count} file change(s)."},
        "plan_original_counts": {"pl": "Kopie istniejących oryginałów: {backups} · nowe ścieżki bez oryginału: {new}.", "en": "Existing-file backups: {backups} · new targets without an original: {new}."},
        "plan_review_hint": {"pl": "Przed wykonaniem sprawdź listę operacji i ewentualne ostrzeżenia.", "en": "Review the operations and any warnings before continuing."},
        "plan_no_changes": {"pl": "Nic nie zostanie zmienione, dopóki nie zatwierdzisz tego planu.", "en": "Nothing will change until you approve this plan."},
        "plan_blocked": {"pl": "Usuń błędy/konflikty i ponów plan. Konflikty nie są nadpisywane.", "en": "Resolve errors/conflicts and create a new plan. Conflicting files are never overwritten."},
        "plan_nothing": {"pl": "Brak zmian do wykonania.", "en": "There are no changes to perform."},
        "plan_cancel": {"pl": "Anuluj", "en": "Cancel"},
        "plan_apply": {"pl": "Zastosuj plan", "en": "Apply plan"},
        "plan_files_heading": {"pl": "PLAN PLIKÓW", "en": "FILE PLAN"},
        "plan_warnings_heading": {"pl": "OSTRZEŻENIA", "en": "WARNINGS"},
        "plan_conflicts_heading": {"pl": "KONFLIKTY (pozostaną bez zmian)", "en": "CONFLICTS (left untouched)"},
        "plan_errors_heading": {"pl": "BŁĘDY", "en": "ERRORS"},
        "plan_source": {"pl": "Źródło", "en": "Source"},
        "plan_target": {"pl": "Cel", "en": "Target"},
        "plan_backup": {"pl": "Kopia oryginału", "en": "Original backup"},
        "plan_action_create": {"pl": "Utwórz link", "en": "Create link"},
        "plan_action_repair": {"pl": "Napraw link", "en": "Repair link"},
        "plan_action_force": {"pl": "Zastąp link innego moda", "en": "Replace another mod's link"},
        "plan_action_already_enabled": {"pl": "Już włączony", "en": "Already enabled"},
        "plan_action_restore_backup": {"pl": "Usuń link i przywróć oryginał", "en": "Remove link and restore original"},
        "plan_action_remove_added": {"pl": "Usuń dodany plik", "en": "Remove added file"},
        "plan_action_restore_missing": {"pl": "Przywróć brakujący oryginał", "en": "Restore missing original"},
        "plan_action_already_missing": {"pl": "Plik już usunięty", "en": "File already removed"},
        "plan_action_preserve_foreign": {"pl": "Pozostaw obcy plik bez zmian", "en": "Leave foreign file untouched"},
        "plan_action_already_disabled": {"pl": "Już wyłączony", "en": "Already disabled"},
        "plan_action_verify": {"pl": "Sprawdź plik", "en": "Verify file"},
        "plan_operation_enable": {"pl": "włącz", "en": "enable"},
        "plan_operation_disable": {"pl": "wyłącz", "en": "disable"},
        "plan_operation_restore": {"pl": "przywróć", "en": "restore"},
        "plan_operation_repair": {"pl": "napraw", "en": "repair"},
        "plan_operation_verify": {"pl": "sprawdź", "en": "verify"},
    }
)


def normalize_language(language: Any) -> str:
    """Zwraca obsługiwany kod języka; nieznane wartości przechodzą na polski."""
    value = str(language or "").strip().casefold().replace("_", "-")
    if value in {"en", "english", "en-us", "en-gb"}:
        return "en"
    if value in {"pl", "polski", "polish", "pl-pl"}:
        return "pl"
    return DEFAULT_LANGUAGE


def language_from_label(label: str) -> str:
    """Mapuje widoczną nazwę opcji wyboru na kod języka."""
    value = label.strip().casefold()
    for code, name in LANGUAGE_LABELS.items():
        if value == name.casefold():
            return code
    return normalize_language(value)


def translate(language: str, key: str, **values: Any) -> str:
    """Tłumaczy klucz GUI i podstawia opcjonalne wartości formatujące."""
    code = normalize_language(language)
    entry = _STRINGS.get(key)
    if entry is None:
        return key
    template = entry.get(code, entry.get(DEFAULT_LANGUAGE, key))
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return template


_CATEGORY_KEYS = {
    "bez kategorii": "category_uncategorized",
    "uncategorized": "category_uncategorized",
    "brak w bibliotece": "category_not_in_library",
    "not in library": "category_not_in_library",
    "camera": "category_camera",
    "kamera": "category_camera",
    "interface": "category_interface",
    "interfejs": "category_interface",
    "ui": "category_interface",
    "graphics": "category_graphics",
    "grafika": "category_graphics",
    "map": "category_map",
    "maps": "category_map",
    "mapa": "category_map",
}


def translate_category(category: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Localizes built-in category labels while preserving user-defined names."""
    key = _CATEGORY_KEYS.get(category.strip().casefold())
    return translate(language, key) if key else category


def translate_category_path(category: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Localizes recognized labels in a nested category path."""
    return "/".join(
        translate_category(segment, language)
        for segment in category.split("/")
    )


def load_language(config_dir: str | Path) -> str:
    """Ładuje preferowany język GUI, domyślnie Polski dla starszych instalacji."""
    path = Path(config_dir) / "ui_settings.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return DEFAULT_LANGUAGE
    if not isinstance(data, dict):
        return DEFAULT_LANGUAGE
    return normalize_language(data.get("language"))


def save_language(config_dir: str | Path, language: str) -> None:
    """Zapisuje preferowany język atomowo poza repozytorium aplikacji."""
    directory = Path(config_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "ui_settings.json"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".ui-settings-",
        suffix=".tmp",
        dir=directory,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump({"language": normalize_language(language)}, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_LABELS",
    "SUPPORTED_LANGUAGES",
    "language_from_label",
    "load_language",
    "normalize_language",
    "save_language",
    "translate",
    "translate_category",
    "translate_category_path",
]
