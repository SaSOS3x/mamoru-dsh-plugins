# install.ps1 - install the skills of this repository into DeepSeek Harness.
#
# By default it creates a junction (directory link) for every skill in
# %USERPROFILE%\.dsh\skills\<skill>. DSH scans that root and watches it, so edits in this
# repository are visible without reinstalling.
#
#   powershell -NoProfile -File install.ps1            create or update the links
#   powershell -NoProfile -File install.ps1 -Copy      copy the folders instead of linking
#   powershell -NoProfile -File install.ps1 -List      show what is installed
#   powershell -NoProfile -File install.ps1 -Remove    remove the links this script made
#   powershell -NoProfile -File install.ps1 -Force     overwrite existing folders or links
#
# -SkillsRoot sets another root (for example <project>\.dsh\skills).
# If the execution policy blocks an unsigned script, add -ExecutionPolicy Bypass to the
# powershell command line (the file is plain text; read it before running it).
#
# Messages are ASCII on purpose: Windows PowerShell 5.1 reads a .ps1 file in the OEM/ANSI
# codepage unless the file has a BOM, and a dropped BOM turns non-ASCII strings into a
# parse error. Keep this file ASCII.

[CmdletBinding()]
param(
    [switch]$Copy,
    [switch]$Remove,
    [switch]$List,
    [switch]$Force,
    [string]$SkillsRoot
)

$ErrorActionPreference = 'Stop'

$repoSkills = Join-Path $PSScriptRoot 'skills'
if (-not (Test-Path -LiteralPath $repoSkills)) {
    Write-Error "Skills folder not found: $repoSkills"
}

if (-not $SkillsRoot) {
    $dshHome = if ($env:DSH_HOME) { $env:DSH_HOME } else { Join-Path $HOME '.dsh' }
    $SkillsRoot = Join-Path $dshHome 'skills'
}

$names = Get-ChildItem -LiteralPath $repoSkills -Directory |
    Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') } |
    ForEach-Object { $_.Name }
if (-not $names) {
    Write-Error "No skills found in $repoSkills (expected <skill>/SKILL.md)"
}

function Get-LinkTarget($path) {
    $item = Get-Item -LiteralPath $path -Force
    if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        $t = @($item.Target)[0]
        if ($t) {
            # Windows PowerShell 5.1 reports a junction target as "Global\C:\..." (or "\\?\C:\...").
            $t = $t -replace '^Global\\', '' -replace '^\\\\\?\\', ''
        }
        return $t
    }
    return $null
}

if ($List) {
    Write-Host "Skills root: $SkillsRoot"
    if (-not (Test-Path -LiteralPath $SkillsRoot)) { Write-Host '  (root does not exist)'; return }
    foreach ($n in $names) {
        $target = Join-Path $SkillsRoot $n
        if (-not (Test-Path -LiteralPath $target)) { Write-Host ("  {0,-32} missing" -f $n); continue }
        $link = Get-LinkTarget $target
        if ($link) { Write-Host ("  {0,-32} link -> {1}" -f $n, $link) }
        else { Write-Host ("  {0,-32} folder (copy)" -f $n) }
    }
    return
}

if ($Remove) {
    foreach ($n in $names) {
        $target = Join-Path $SkillsRoot $n
        if (-not (Test-Path -LiteralPath $target)) { continue }
        $link = Get-LinkTarget $target
        if ($link) {
            # Delete only the link: deleting a junction does not touch its target.
            (Get-Item -LiteralPath $target -Force).Delete()
            Write-Host "removed link $n"
        }
        else {
            Write-Host "skipped ${n}: not a link (a copied folder is the user's to delete)"
        }
    }
    return
}

if (-not (Test-Path -LiteralPath $SkillsRoot)) {
    New-Item -ItemType Directory -Path $SkillsRoot -Force | Out-Null
}

foreach ($n in $names) {
    $source = Join-Path $repoSkills $n
    $target = Join-Path $SkillsRoot $n
    if (Test-Path -LiteralPath $target) {
        $link = Get-LinkTarget $target
        $ours = $link -and ($link.TrimEnd('\') -eq $source.TrimEnd('\'))
        if ($ours -and -not $Copy) { Write-Host "already installed: $n"; continue }
        if (-not $Force) {
            Write-Host "skipped ${n}: $target already exists (use -Force to overwrite)"
            continue
        }
        if ($link) { (Get-Item -LiteralPath $target -Force).Delete() }
        else { Remove-Item -LiteralPath $target -Recurse -Force }
    }
    if ($Copy) {
        Copy-Item -LiteralPath $source -Destination $target -Recurse
        Write-Host "copied: $n"
    }
    else {
        New-Item -ItemType Junction -Path $target -Target $source | Out-Null
        Write-Host "linked: $n -> $source"
    }
}

Write-Host ''
Write-Host "Done. Skills root: $SkillsRoot"
Write-Host 'DSH picks the skills up in the session catalog; an open session refreshes it by itself.'
