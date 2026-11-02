<#
.SYNOPSIS
    Parse-validate every embedded PowerShell command inside a .cmd/.bat file,
    and optionally a PS1 test harness, using the real PowerShell parser.

.DESCRIPTION
    extract_ps.py gives a fast dependency-free lint, but only the actual
    PowerShell language parser can tell you a one-liner is genuinely valid.
    This script extracts each `powershell ... -Command "..."` body and runs it
    through [System.Management.Automation.Language.Parser]::ParseInput, and can
    also parse-check (and run) a harness such as tests/Run-Tests.ps1.

    Exit code is nonzero if any snippet or the harness fails to parse, so it
    slots into CI next to the batch analyzer. Exit codes: 0 = valid (or no
    embedded PowerShell found - a warning is printed then), 1 = a snippet or the
    harness is bad, 2 = a file named on the command line does not exist.

    Works in Windows PowerShell 5.1 (powershell.exe, built into Windows) and in
    pwsh 7. In a snippet, \" (the way powershell.exe's command line writes a
    quote) is turned into " before parsing.

.PARAMETER CmdFile
    Path to the .cmd/.bat file whose embedded PowerShell should be validated.

.PARAMETER Harness
    Optional path to a .ps1 test harness to parse-check.

.PARAMETER RunHarness
    If set, also execute the harness (after it parses cleanly).

.EXAMPLE
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File Validate-Embedded.ps1 -CmdFile PerfTweaks.cmd
    powershell -NoProfile -File Validate-Embedded.ps1 -CmdFile PerfTweaks.cmd
    powershell -NoProfile -File Validate-Embedded.ps1 -CmdFile PerfTweaks.cmd -Harness tests/Run-Tests.ps1 -RunHarness
#>
param(
    [Parameter(Mandatory = $true)] [string] $CmdFile,
    [string] $Harness,
    [switch] $RunHarness
)

$ErrorActionPreference = 'Stop'
$failures = 0

# Parser messages are localized. When the output goes to a pipe (Git Bash, an agent's shell tool) Windows
# PowerShell encodes it in the OEM code page (cp866 on a Russian Windows) and the caller shows garbage.
# Use UTF-8 for this run only and give the console its encoding back on every exit.
$script:prevOutEnc = $null
if ([Console]::IsOutputRedirected) {
    try {
        $script:prevOutEnc = [Console]::OutputEncoding
        [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    } catch { $script:prevOutEnc = $null }
}
function Exit-Script([int] $code) {
    if ($script:prevOutEnc) { try { [Console]::OutputEncoding = $script:prevOutEnc } catch { } }
    exit $code
}

function Test-Snippet([string] $code) {
    $errs = $null
    [System.Management.Automation.Language.Parser]::ParseInput(
        $code, [ref]$null, [ref]$errs) | Out-Null
    return $errs
}

# Exit codes (documented): 0 = all valid, 1 = a snippet or the harness is bad,
# 2 = a file named on the command line does not exist. Write-Error would throw
# under $ErrorActionPreference = 'Stop' and turn the 2 into a 1, so print instead.
if (-not (Test-Path -LiteralPath $CmdFile)) {
    [Console]::Error.WriteLine("CmdFile not found: $CmdFile")
    Exit-Script 2
}

$text = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $CmdFile))

# Same shape as extract_ps.py: powershell|pwsh ... -Command "body", with \" treated
# as an escaped quote so commands containing literal quotes aren't truncated.
$rx = [regex]'(?i)\b(?:powershell|pwsh)\b[^"\r\n]*?\s(?:-Command|-c|/c)\s+"((?:[^"\\]|\\.)*)"'
$found = $rx.Matches($text)

Write-Host "Found $($found.Count) embedded PowerShell command(s) in $CmdFile"
$idx = 0
foreach ($m in $found) {
    $idx++
    # Inside the cmd line, \" is how the powershell.exe command line writes a quote;
    # the PowerShell parser must see the quote itself, not the backslash.
    $code = $m.Groups[1].Value.Replace('\"', '"')
    $errs = Test-Snippet $code
    if ($errs.Count -eq 0) {
        Write-Host ("  [OK ] snippet #{0} ({1} chars)" -f $idx, $code.Length)
    }
    else {
        $failures++
        $preview = $code.Substring(0, [Math]::Min(70, $code.Length))
        Write-Host ("  [BAD] snippet #{0}: {1}..." -f $idx, $preview)
        foreach ($e in $errs) { Write-Host ("        - " + $e.Message) }
    }
}

if ($Harness) {
    if (-not (Test-Path -LiteralPath $Harness)) {
        [Console]::Error.WriteLine("Harness not found: $Harness")
        Exit-Script 2
    }
    $herrs = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        (Resolve-Path -LiteralPath $Harness), [ref]$null, [ref]$herrs) | Out-Null
    if ($herrs.Count -eq 0) {
        Write-Host "Harness parses clean: $Harness"
    }
    else {
        $failures++
        Write-Host "Harness PARSE ERRORS in ${Harness}:"
        foreach ($e in $herrs) { Write-Host ("  - " + $e.Message) }
    }

    if ($RunHarness -and $herrs.Count -eq 0) {
        Write-Host "`n--- running harness ---"
        & (Resolve-Path -LiteralPath $Harness)
        if ($LASTEXITCODE -ne 0) {
            $failures++
            Write-Host "Harness exited with code $LASTEXITCODE"
        }
    }
}

Write-Host ""
if ($failures -gt 0) {
    Write-Host "FAILED: $failures problem(s)."
    Exit-Script 1
}
if ($found.Count -eq 0) {
    # Nothing was parsed: do not print the green line. Either the file has no
    # embedded PowerShell, or the regex missed the way it is written (e.g. the
    # body is not in double quotes, or it is built from variables).
    Write-Host "WARNING: no embedded PowerShell found in $CmdFile - nothing was validated."
    if ($Harness) { Write-Host "(The harness was checked above.)" }
    Exit-Script 0
}
Write-Host "All embedded PowerShell valid ($($found.Count) command(s) checked)."
Exit-Script 0
