# Shared helpers for the Docker wrappers. Sourced, not executed.
# Docker Desktop on Windows wants F:/... paths; on Linux cygpath is missing and the path stays as is.
winpath() { cygpath -m "$1" 2>/dev/null || printf '%s' "$1"; }
export MSYS_NO_PATHCONV=1
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(winpath "$REPO_ROOT")"
SSH_DIR="$(winpath "${SSH_DIR:-$HOME/.ssh}")"
