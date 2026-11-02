# install.ps1 - install the skills of this repository into DeepSeek Harness.
#
# Skills live in components: skills/core/<skill> and skills/minecraft/<skill>. This script
# installs every skill as a flat folder under %USERPROFILE%\.dsh\skills\<skill> (the
# filesystem provider scans that root), so the component layout stays a repository detail.
#
# By default it creates a junction (directory link) for every skill, so edits in this
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

# Flatten components: skills/<component>/<skill>/SKILL.md -> name <skill>, source <folder>.
$skills = @()
foreach ($group in Get-ChildItem -LiteralPath $repoSkills -Directory) {
    foreach ($skill in Get-ChildItem -LiteralPath $group.FullName -Directory) {
        if (Test-Path -LiteralPath (Join-Path $skill.FullName 'SKILL.md')) {
            $skills += [pscustomobject]@{ Name = $skill.Name; Source = $skill.FullName }
        }
    }
}
if (-not $skills) {
    Write-Error "No skills found under $repoSkills (expected skills/<component>/<skill>/SKILL.md)"
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
    foreach ($s in $skills) {
        $target = Join-Path $SkillsRoot $s.Name
        if (-not (Test-Path -LiteralPath $target)) { Write-Host ("  {0,-32} missing" -f $s.Name); continue }
        $link = Get-LinkTarget $target
        if ($link) { Write-Host ("  {0,-32} link -> {1}" -f $s.Name, $link) }
        else { Write-Host ("  {0,-32} folder (copy)" -f $s.Name) }
    }
    return
}

if ($Remove) {
    foreach ($s in $skills) {
        $target = Join-Path $SkillsRoot $s.Name
        if (-not (Test-Path -LiteralPath $target)) { continue }
        $link = Get-LinkTarget $target
        if ($link) {
            # Delete only the link: deleting a junction does not touch its target.
            (Get-Item -LiteralPath $target -Force).Delete()
            Write-Host "removed link $($s.Name)"
        }
        else {
            Write-Host "skipped $($s.Name): not a link (a copied folder is the user's to delete)"
        }
    }
    return
}

if (-not (Test-Path -LiteralPath $SkillsRoot)) {
    New-Item -ItemType Directory -Path $SkillsRoot -Force | Out-Null
}

foreach ($s in $skills) {
    $source = $s.Source
    $target = Join-Path $SkillsRoot $s.Name
    if (Test-Path -LiteralPath $target) {
        $link = Get-LinkTarget $target
        $ours = $link -and ($link.TrimEnd('\') -eq $source.TrimEnd('\'))
        if ($ours -and -not $Copy) { Write-Host "already installed: $($s.Name)"; continue }
        if (-not $Force) {
            Write-Host "skipped $($s.Name): $target already exists (use -Force to overwrite)"
            continue
        }
        if ($link) { (Get-Item -LiteralPath $target -Force).Delete() }
        else { Remove-Item -LiteralPath $target -Recurse -Force }
    }
    if ($Copy) {
        Copy-Item -LiteralPath $source -Destination $target -Recurse
        Write-Host "copied: $($s.Name)"
    }
    else {
        New-Item -ItemType Junction -Path $target -Target $source | Out-Null
        Write-Host "linked: $($s.Name) -> $source"
    }
}

Write-Host ''
Write-Host "Done. Skills root: $SkillsRoot"
Write-Host 'DSH picks the skills up in the session catalog; an open session refreshes it by itself.'
