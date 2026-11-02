#!/usr/bin/env bash
# setup_pwsh.sh - install PowerShell from the official tarball when it isn't
# already available, so Validate-Embedded.ps1 and any Run-Tests.ps1 harness can
# run under the real interpreter.
#
# LINUX ONLY. The sandbox frequently has no pwsh. Rather than skip real
# parse-validation, drop in the portable Linux build. Idempotent: if pwsh is
# already on PATH or already installed at the target, it just prints the path.
# On Windows it refuses (use powershell.exe 5.1, see Validate-Embedded.ps1).
#
# Usage:  bash setup_pwsh.sh [version]
#         eval "$(bash setup_pwsh.sh --print-path)"   # to get PWSH=... for a caller
set -euo pipefail

VERSION="${1:-7.4.6}"
[ "${VERSION}" = "--print-path" ] && VERSION="7.4.6" && PRINT_ONLY=1 || PRINT_ONLY=0
TARGET="/opt/pwsh"
BIN="${TARGET}/pwsh"

# Already on PATH?
if command -v pwsh >/dev/null 2>&1; then
    [ "${PRINT_ONLY}" = "1" ] && echo "PWSH=$(command -v pwsh)" || \
        echo "pwsh already on PATH: $(command -v pwsh) ($(pwsh -v 2>/dev/null))"
    exit 0
fi

# This script installs the LINUX build of PowerShell into /opt/pwsh. On Windows
# (Git Bash / MSYS / Cygwin: uname is MINGW64_NT-..., MSYS_NT-..., CYGWIN_NT-...)
# and on macOS that build cannot run, so refuse before downloading anything.
if [ "$(uname -s)" != "Linux" ]; then
    echo "setup_pwsh.sh: refused - this installs the Linux build of PowerShell and this system is '$(uname -s)'." >&2
    echo "On Windows no install is needed: Windows PowerShell 5.1 (powershell.exe) is built in and runs Validate-Embedded.ps1:" >&2
    echo "  powershell.exe -NoProfile -ExecutionPolicy Bypass -File <skill folder>/scripts/Validate-Embedded.ps1 -CmdFile script.cmd" >&2
    exit 1
fi

# Already installed at target?
if [ -x "${BIN}" ]; then
    [ "${PRINT_ONLY}" = "1" ] && echo "PWSH=${BIN}" || \
        echo "pwsh present at ${BIN} ($(${BIN} -v 2>/dev/null))"
    exit 0
fi

# Detect arch.
case "$(uname -m)" in
    x86_64|amd64) ARCH="x64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;;
esac

URL="https://github.com/PowerShell/PowerShell/releases/download/v${VERSION}/powershell-${VERSION}-linux-${ARCH}.tar.gz"

if [ "${PRINT_ONLY}" != "1" ]; then
    echo "Installing PowerShell ${VERSION} (${ARCH}) from official tarball..."
fi

TMP="$(mktemp -d)"
curl -sSL -o "${TMP}/pwsh.tar.gz" "${URL}"
mkdir -p "${TARGET}"
tar -xzf "${TMP}/pwsh.tar.gz" -C "${TARGET}"
chmod +x "${BIN}"
rm -rf "${TMP}"

if [ "${PRINT_ONLY}" = "1" ]; then
    echo "PWSH=${BIN}"
else
    echo "Installed: ${BIN} ($(${BIN} -v))"
    echo "Run with:  ${BIN} -NoProfile -File <script.ps1>"
fi
