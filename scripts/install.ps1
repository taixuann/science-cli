#Requires -Version 5.1

<#
.SYNOPSIS
    Installs science-cli and its dependencies (Python, fzf) on Windows.
.DESCRIPTION
    Checks for Python 3.9+, installs fzf binary from GitHub Releases,
    installs science-cli via pip/pipx, and initializes configuration.
.NOTES
    Author: science-cli team
    Requires: Windows 10/11, PowerShell 5.1+
#>

$Host.UI.RawUI.WindowTitle = "Installing science-cli…"

$ErrorActionPreference = "Stop"
$WarningPreference = "Continue"

# ── Config ─────────────────────────────────────────────────────
$PackageName = "science-cli"
$FzfVersion = "0.73.1"
$FzfUrl = "https://github.com/junegunn/fzf/releases/download/v$FzfVersion/fzf-$FzfVersion-windows_amd64.zip"
$FzfSha256Expected = "5C4A0843C75153BF8282625290AB4E2584EBD8BAE22E86C372DB4C8F5146ADE7"
$InstallBinDir = Join-Path $env:LOCALAPPDATA "science-cli\bin"
$FzfPath = Join-Path $InstallBinDir "fzf.exe"

# ── Helper functions ───────────────────────────────────────────
function Write-Step($Text) {
    Write-Host "  → $Text"
}

function Write-Success($Text) {
    Write-Host "  ✓ $Text" -ForegroundColor Green
}

function Write-Warn($Text) {
    Write-Host "  ⚠ $Text" -ForegroundColor Yellow
}

function Write-Error($Text) {
    Write-Host "  ✗ $Text" -ForegroundColor Red
}

function Test-Command($Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

# ── 1. Check Python 3.9+ ──────────────────────────────────────
Write-Host "`n── Checking Python ──`n" -ForegroundColor Cyan

$pythonPath = $null
try {
    $versionOutput = & python --version 2>&1
    if ($versionOutput -match "Python (\d+)\.(\d+)") {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -ge 3 -and $minor -ge 9) {
            $pythonPath = (Get-Command python).Source
            Write-Success "Python $major.$minor found: $pythonPath"
        } else {
            Write-Warn "Python $major.$minor is too old (need 3.9+)."
        }
    }
} catch {
    Write-Step "Python not found."
}

if (-not $pythonPath) {
    Write-Warn "Python 3.9+ is required but not installed."
    if (Test-Command winget) {
        $choice = Read-Host "  Install Python 3.11 via winget? [Y/n]"
        if ($choice -ne "n" -and $choice -ne "N") {
            Write-Step "Installing Python 3.11 via winget…"
            try {
                winget install "Python.Python.3.11" --accept-package-agreements --accept-source-agreements
                # Refresh PATH
                $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";$env:Path"
                $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";$env:Path"
                # Re-check
                $versionOutput = & python --version 2>&1
                if ($versionOutput -match "Python (\d+)\.(\d+)") {
                    $pythonPath = (Get-Command python).Source
                    Write-Success "Python installed: $pythonPath"
                } else {
                    throw "Python installed but not detected in PATH."
                }
            } catch {
                Write-Error "Failed to install Python via winget: $_"
                Write-Step "Download Python manually from: https://www.python.org/downloads/"
                Write-Step "Make sure to check 'Add Python to PATH' during installation."
                exit 1
            }
        } else {
            Write-Step "Skipping Python installation."
            Write-Step "Download Python from: https://www.python.org/downloads/"
            exit 1
        }
    } else {
        Write-Error "winget not available (requires Windows 10 1809+ or Windows 11)."
        Write-Step "Download Python manually from: https://www.python.org/downloads/"
        Write-Step "Make sure to check 'Add Python to PATH' during installation."
        exit 1
    }
}

# ── 2. Install fzf ─────────────────────────────────────────────
Write-Host "`n── Installing fzf ──`n" -ForegroundColor Cyan

if (Test-Command fzf) {
    $fzfVer = & fzf --version 2>&1
    Write-Success "fzf already installed ($fzfVer)"
} elseif (Test-Path $FzfPath) {
    Write-Success "fzf already installed at $FzfPath"
} else {
    Write-Step "Downloading fzf $FzfVersion…"
    try {
        # Ensure bin directory exists
        New-Item -ItemType Directory -Force -Path $InstallBinDir | Out-Null

        $zipPath = Join-Path $env:TEMP "fzf-$FzfVersion-windows_amd64.zip"
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            curl.exe -fsSL $FzfUrl -o $zipPath
        } else {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $FzfUrl -OutFile $zipPath -UseBasicParsing
        }

        # Verify SHA256
        Write-Step "Verifying checksum…"
        $actualHash = (Get-FileHash -Path $zipPath -Algorithm SHA256).Hash
        if ($actualHash -ne $FzfSha256Expected) {
            Write-Warn "SHA256 mismatch!"
            Write-Warn "  Expected: $FzfSha256Expected"
            Write-Warn "  Actual:   $actualHash"
            $proceed = Read-Host "  Proceed anyway? [y/N]"
            if ($proceed -ne "y" -and $proceed -ne "Y") {
                Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
                exit 1
            }
        } else {
            Write-Success "Checksum verified"
        }

        # Extract
        Write-Step "Extracting fzf…"
        try {
            Expand-Archive -Path $zipPath -DestinationPath $InstallBinDir -Force
        } catch {
            # Fallback: use System.IO.Compression.ZipFile
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, $InstallBinDir, $true)
        }
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

        # Ensure fzf.exe exists
        if (-not (Test-Path $FzfPath)) {
            # Might be in a subfolder
            $extracted = Get-ChildItem $InstallBinDir -Recurse -Filter "fzf.exe" | Select-Object -First 1
            if ($extracted) {
                Move-Item $extracted.FullName $FzfPath -Force
            } else {
                throw "fzf.exe not found after extraction"
            }
        }

        Write-Success "fzf installed to $FzfPath"
    } catch {
        Write-Error "Failed to install fzf: $_"
        Write-Step "Download manually from: https://github.com/junegunn/fzf/releases"
    }
}

# Add fzf to PATH (user-level)
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$InstallBinDir*") {
    Write-Step "Adding $InstallBinDir to user PATH…"
    $newPath = "$InstallBinDir;$currentPath"
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    $env:Path = "$InstallBinDir;$env:Path"
    Write-Success "Added to PATH"
}

# ── 3. Install science-cli ────────────────────────────────────
Write-Host "`n── Installing $PackageName ──`n" -ForegroundColor Cyan

$installed = $false

# Prefer pipx
if (Test-Command pipx) {
    $pipxList = & pipx list 2>&1
    if ($pipxList -match $PackageName) {
        Write-Success "$PackageName already installed via pipx"
        Write-Step "Upgrading…"
        pipx upgrade $PackageName
        $installed = $true
    } else {
        Write-Step "Installing via pipx…"
        try {
            pipx install $PackageName
            $installed = $true
            Write-Success "Installed via pipx"
        } catch {
            Write-Warn "pipx install failed: $_"
        }
    }
} else {
    Write-Step "pipx not available — trying to install it…"
    try {
        & python -m pip install --user pipx
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
        if (Test-Command pipx) {
            pipx install $PackageName
            $installed = $true
            Write-Success "Installed via pipx"
        }
    } catch {
        Write-Warn "Could not set up pipx"
    }
}

# Fallback to pip
if (-not $installed) {
    # Check if already installed via pip
    $pipList = & python -m pip list --format=columns 2>&1
    if ($pipList -match $PackageName) {
        Write-Success "$PackageName already installed via pip"
        Write-Step "Upgrading…"
        & python -m pip install --upgrade $PackageName
        $installed = $true
    } else {
        Write-Step "Installing via pip (user install)…"
        try {
            & python -m pip install --user $PackageName
            $installed = $true
            Write-Success "Installed via pip"

            # Ensure pip user bin is on PATH
            $pipUserBin = Join-Path $env:USERPROFILE ".local\bin"
            if (-not (Test-Path $pipUserBin)) {
                $pipUserBin = Join-Path $env:APPDATA "Python\Scripts"
            }
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
            if ($currentPath -notlike "*$pipUserBin*" -and (Test-Path $pipUserBin)) {
                Write-Step "Adding $pipUserBin to user PATH…"
                [Environment]::SetEnvironmentVariable("Path", "$pipUserBin;$currentPath", "User")
                $env:Path = "$pipUserBin;$env:Path"
            }
        } catch {
            Write-Error "pip install failed: $_"
            exit 1
        }
    }
}

# ── 4. Initialize config ──────────────────────────────────────
Write-Host "`n── Configuration ──`n" -ForegroundColor Cyan
try {
    if (Test-Command sci) {
        & sci config init 2>$null
        Write-Success "science-cli initialized"
    } else {
        Write-Warn "sci command not on PATH yet."
        Write-Step "After restarting your terminal, run: sci config init"
    }
} catch {
    Write-Warn "Config init skipped (run 'sci config init' manually after restarting terminal)"
}

# ── 5. Success ────────────────────────────────────────────────
Write-Host "`n── Installation Complete ──`n" -ForegroundColor Cyan
Write-Host ""
Write-Host "  $(sci --version 2>$null)" -ForegroundColor Green
Write-Host ""
Write-Host "  Quick start:" -ForegroundColor White
Write-Host "    sci --help`t`tShow all commands" -ForegroundColor Cyan
Write-Host "    sci --repl`t`tLaunch interactive REPL" -ForegroundColor Cyan
Write-Host "    sci`t`t`tLaunch full TUI" -ForegroundColor Cyan
Write-Host "    sci add -m project -n my-experiment  Create a project" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Documentation: https://github.com/taixuann/science-cli" -ForegroundColor White
Write-Host ""
Write-Warn "You may need to restart your terminal for PATH changes to take effect."
Write-Host ""

# Check PowerShell execution policy
$currentPolicy = Get-ExecutionPolicy -Scope CurrentUser
if ($currentPolicy -eq "Restricted") {
    Write-Warn "Execution policy is Restricted. To run scripts in the future, run:"
    Write-Host "  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned" -ForegroundColor Cyan
}
