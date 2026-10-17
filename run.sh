#!/usr/bin/env bash
# The system python3 is the one with PyGObject/GTK4 bindings.
set -euo pipefail
cd "$(dirname "$0")"
exec /usr/bin/python3 src/reacalc/__main__.py "$@"
