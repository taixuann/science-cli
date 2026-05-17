#!/usr/bin/env bash
set -euo pipefail

RST="\033[0m"
RED="\033[0;31m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
BLUE="\033[0;34m"

info()  { echo -e "  ${BLUE}•${RST}  $*"; }
ok()    { echo -e "  ${GREEN}✓${RST}  $*"; }
warn()  { echo -e "  ${YELLOW}⚠${RST}  $*"; }
die()   { echo -e "  ${RED}✗${RST}  $*" >&2; exit 1; }

PYPI_PACKAGE="science-cli"
BIN_DIR="${HOME}/.local/bin"
VENV_DIR="${HOME}/.local/share/science-cli"

echo ""
echo "  ╭──────────────────────────────────────╮"
echo "  │  science-cli  —  one-line install    │"
echo "  ╰──────────────────────────────────────╯"
echo ""

# ── detect python ────────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
if [[ -z "$PYTHON" ]]; then
    die "Python 3.9+ not found. Install it first: https://python.org/downloads"
fi
info "Using $("$PYTHON" --version)"

# ── detect / install pipx ─────────────────────────────────────────────
INSTALL_MODE=""
if command -v pipx &>/dev/null; then
    INSTALL_MODE="pipx"
    ok "pipx already installed"
elif command -v uv &>/dev/null; then
    INSTALL_MODE="uv"
    ok "uv already installed"
else
    warn "pipx not found — installing via pip (or try: brew install pipx)"
    "$PYTHON" -m pip install --user pipx -q
    "$PYTHON" -m pipx ensurepath &>/dev/null || true
    if command -v pipx &>/dev/null; then
        INSTALL_MODE="pipx"
        ok "pipx installed"
    else
        # fallback: direct pip install into venv
        INSTALL_MODE="venv"
        info "Falling back to isolated venv install"
    fi
fi

# ── install science-cli ───────────────────────────────────────────────
case "$INSTALL_MODE" in
    pipx)
        info "Installing $PYPI_PACKAGE via pipx..."
        pipx install "$PYPI_PACKAGE" -q
        ;;
    uv)
        info "Installing $PYPI_PACKAGE via uv..."
        uv tool install "$PYPI_PACKAGE" -q
        ;;
    venv)
        info "Creating venv at $VENV_DIR..."
        "$PYTHON" -m venv "$VENV_DIR"
        "$VENV_DIR/bin/pip" install --quiet --upgrade pip
        "$VENV_DIR/bin/pip" install --quiet "$PYPI_PACKAGE"
        mkdir -p "$BIN_DIR"
        ln -sf "$VENV_DIR/bin/sci" "$BIN_DIR/sci"
        warn "Add $BIN_DIR to your PATH if not already:"
        warn "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc"
        ;;
esac

# ── verify ────────────────────────────────────────────────────────────
if command -v sci &>/dev/null; then
    found="$(sci --version 2>/dev/null || echo "ok")"
    ok "science-cli ready! ($found)"
else
    warn "sci not found on PATH yet."
    warn "Run:  export PATH=\"\$HOME/.local/bin:\$PATH\""
    warn "Then try: sci --help"
fi

echo ""
info "Next steps:"
info "  sci config init              # create config"
info "  sci --help                   # see commands"
info "  sci config edit --global     # set projects_root"
echo ""
