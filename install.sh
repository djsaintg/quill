#!/usr/bin/env bash
# Puts `quill` and `plume` on your PATH and (optionally) makes typing `claude` open Quill.
#   ./install.sh           quill command only
#   ./install.sh --alias   also: claude -> quill   (plain Claude Code stays at: command claude)
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
mkdir -p "$HOME/.local/bin"
ln -sf "$DIR/bin/quill" "$HOME/.local/bin/quill"
ln -sf "$DIR/bin/quill" "$HOME/.local/bin/plume"
echo "✓ quill and plume -> $HOME/.local/bin/ (each opens its own character)"
if [[ "${1:-}" == "--alias" ]]; then
  LINE="alias claude='quill'  # Quill: plain Claude Code is 'command claude'"
  for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [[ -f "$rc" ]] || continue
    if ! grep -qF "$LINE" "$rc"; then
      printf '\n%s\n' "$LINE" >> "$rc"
    fi
    echo "✓ alias added to $rc (open a new terminal)"
  done
  if command -v fish >/dev/null; then
    echo "fish users: run  alias --save claude=quill"
  fi
fi
