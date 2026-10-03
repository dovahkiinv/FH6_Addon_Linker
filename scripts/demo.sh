#!/usr/bin/env bash
# Smoke test CLI end-to-end na bezpiecznej, tymczasowej atrapce gry.
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT

cd "$PROJECT_ROOT"
export FH6LINKER_CONFIG_DIR="$TEMP_ROOT/config"
GAME="$TEMP_ROOT/game"
LIBRARY="$TEMP_ROOT/mods"
BACKUPS="$TEMP_ROOT/backups"

python - "$GAME" "$LIBRARY" <<'PY'
from pathlib import Path
import sys

game = Path(sys.argv[1])
library = Path(sys.argv[2])
(game / "media/Audio/FMODBanks").mkdir(parents=True)
(game / "forzahorizon6.exe").write_bytes(b"fake game")
(game / "media/Audio/FMODBanks/engine.bank").write_bytes(b"vanilla sound")
source = library / "Audio/Demo/media/Audio/FMODBanks/engine.bank"
source.parent.mkdir(parents=True)
source.write_bytes(b"modded sound")
PY

python -m fh6linker set --game "$GAME" --library "$LIBRARY" --backup-dir "$BACKUPS" --method auto
python -m fh6linker scan
python -m fh6linker enable Demo --dry-run
python -m fh6linker enable Demo
python -m fh6linker status
python -m fh6linker disable Demo
python -m fh6linker enable Demo
python -m fh6linker restore --yes

echo "Demo zakończone — oryginalny plik gry został przywrócony."
