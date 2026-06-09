#!/usr/bin/env bash
set -euo pipefail

REPO="taixuann/science-cli"
FZF_VERSION="0.73.1"
PACKAGE="science-cli"

# ── Color helpers ──────────────────────────────────────────────
bold()   { printf "\033[1m%s\033[0m" "$*"; }
green()  { printf "\033[32m%s\033[0m" "$*"; }
red()    { printf "\033[31m%s\033[0m" "$*"; }
yellow() { printf "\033[33m%s\033[0m" "$*"; }

info()    { printf "  %s\n" "$*"; }
success() { printf "  %s %s\n" "$(green "✓")" "$*"; }
warn()    { printf "  %s %s\n" "$(yellow "⚠")" "$*"; }
fail()    { printf "  %s %s\n" "$(red "✗")" "$*"; exit 1; }
header()  { printf "\n── %s ──\n\n" "$(bold "$*")"; }

# ── Detect platform ────────────────────────────────────────────
UNAME="$(uname -s)"
case "$UNAME" in
    Darwin)  OS="macos"   ;;
    Linux)   OS="linux"   ;;
    *)       fail "Unsupported OS: $UNAME (only macOS/Linux)" ;;
esac

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64) ARCH_SUFFIX="amd64" ;;
    aarch64|arm64) ARCH_SUFFIX="arm64" ;;
    *)            fail "Unsupported arch: $ARCH" ;;
esac

header "science-cli Installer (macOS / Linux)"

# ── 1. Check Python 3.9+ ───────────────────────────────────────
info "Checking Python…"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        ver="$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+')"
        major="${ver%.*}"
        minor="${ver#*.}"
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    cat <<MSG
  $(red "✗") Python 3.9+ not found.
  Install Python from: https://www.python.org/downloads/
  Or via package manager:
    macOS: brew install python@3.12
    Linux: sudo apt install python3 python3-pip python3-venv  (Debian/Ubuntu)
           sudo dnf install python3 python3-pip               (Fedora)
MSG
    exit 1
fi

py_ver="$("$PYTHON" --version 2>&1 | grep -oP '\d+\.\d+\.\d+')"
success "Python $py_ver found ($(command -v "$PYTHON"))"

# ── 2. Install fzf ─────────────────────────────────────────────
header "Installing fzf"

install_fzf_binary() {
    local url arch_flag
    if [ "$OS" = "macos" ]; then
        arch_flag="darwin_${ARCH_SUFFIX}"
    else
        arch_flag="linux_${ARCH_SUFFIX}"
    fi
    url="https://github.com/junegunn/fzf/releases/download/v${FZF_VERSION}/fzf-${FZF_VERSION}-${arch_flag}.tar.gz"

    local dest="${PREFIX:-$HOME}/.local/bin"
    mkdir -p "$dest"

    info "Downloading fzf ${FZF_VERSION} (${arch_flag})…"
    if command -v curl &>/dev/null; then
        curl -fsSL "$url" -o /tmp/fzf.tar.gz
    elif command -v wget &>/dev/null; then
        wget -q "$url" -O /tmp/fzf.tar.gz
    else
        fail "Need curl or wget to download fzf"
    fi

    tar xzf /tmp/fzf.tar.gz -C "$dest" fzf
    rm -f /tmp/fzf.tar.gz
    chmod +x "$dest/fzf"
    success "fzf installed to $dest/fzf"
}

if command -v fzf &>/dev/null; then
    fzf_ver="$(fzf --version 2>&1 | awk '{print $1}')"
    success "fzf already installed ($fzf_ver)"
elif [ "$OS" = "macos" ] && command -v brew &>/dev/null; then
    info "Installing fzf via Homebrew…"
    brew install fzf
    success "fzf installed via Homebrew"
else
    install_fzf_binary
fi

# ── 3. Install science-cli ─────────────────────────────────────
header "Installing $PACKAGE"

install_via_pipx() {
    if command -v pipx &>/dev/null; then
        info "Installing via pipx…"
        pipx install "$PACKAGE"
        return 0
    fi
    info "pipx not found — installing pipx…"
    if "$PYTHON" -m pip install --user pipx 2>/dev/null; then
        # Refresh PATH for pipx
        export PATH="$HOME/.local/bin:$PATH"
        if command -v pipx &>/dev/null; then
            info "Installing via pipx…"
            pipx install "$PACKAGE"
            return 0
        fi
    fi
    return 1
}

install_via_venv() {
    local venv_dir="${HOME}/.science-cli-venv"
    info "Installing via venv (fallback)…"
    "$PYTHON" -m venv "$venv_dir"
    source "$venv_dir/bin/activate"
    pip install --quiet "$PACKAGE"
    mkdir -p "${HOME}/.local/bin"
    cat > "${HOME}/.local/bin/sci" <<SCRIPT
#!/usr/bin/env bash
source "${venv_dir}/bin/activate"
exec python -m science_cli "\$@"
SCRIPT
    chmod +x "${HOME}/.local/bin/sci"
    success "Created launcher at ${HOME}/.local/bin/sci"
}

# Check if already installed
if command -v sci &>/dev/null; then
    existing_ver="$(sci --version 2>&1 || true)"
    success "science-cli already installed ($existing_ver)"
    header "Upgrading"
    if command -v pipx &>/dev/null && pipx list 2>/dev/null | grep -q "$PACKAGE"; then
        pipx upgrade "$PACKAGE"
    elif [ -d "${HOME}/.science-cli-venv" ]; then
        source "${HOME}/.science-cli-venv/bin/activate"
        pip install --quiet --upgrade "$PACKAGE"
    else
        "$PYTHON" -m pip install --user --upgrade "$PACKAGE"
    fi
    success "Upgraded to latest version"
elif install_via_pipx; then
    success "Installed via pipx"
else
    install_via_venv
    success "Installed via venv"
fi

# ── 4. Initialize config ──────────────────────────────────────
header "Configuration"
if command -v sci &>/dev/null; then
    sci config init 2>/dev/null || sci --help &>/dev/null
    success "science-cli initialized"
else
    warn "sci command not on PATH — run 'sci config init' after adding to PATH"
fi

# ── 5. PATH check ─────────────────────────────────────────────
header "PATH Check"

check_path() {
    local dir="$1"
    if [ -d "$dir" ]; then
        case ":$PATH:" in
            *":$dir:"*) return 0 ;;
            *) return 1 ;;
        esac
    fi
    return 2
}

missing_paths=""
for d in "${HOME}/.local/bin" "${HOME}/.cargo/bin"; do
    if ! check_path "$d"; then
        missing_paths="${missing_paths}export PATH=\"$d:\$PATH\"\n"
    fi
done

if [ -n "$missing_paths" ]; then
    warn "Some bin directories are not on your PATH."
    info "Add the following to your ~/.bashrc, ~/.zshrc, or ~/.profile:"
    printf "%b" "$missing_paths"
    info "Then run: source ~/.zshrc (or source ~/.bashrc)"
fi

# ── 6. Success ────────────────────────────────────────────────
header "Installation Complete"
cat <<MSG
  $(bold "science-cli") is ready.

  Quick start:
    $(green "sci --help")         Show all commands
    $(green "sci --repl")         Launch interactive REPL
    $(green "sci")                Launch full TUI
    $(green "sci add -m project -n my-experiment")  Create a project

  Documentation:
    https://github.com/$REPO

MSG
