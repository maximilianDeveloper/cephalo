# setup.ps1
#
# cephalo setup script (Windows PowerShell).
# Creates project structure based on user choices.
#
# Run as Administrator if you want symlinks (for multi-project setups).
#
# Usage:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup.ps1

[CmdletBinding()]
param(
    [string]$WorkType = "",        # empty = ask interactively
    [string]$Structure = "",
    [string]$Scaffolding = "",
    [string]$Target = "",          # empty = ask or stay here
    [switch]$NonInteractive = $false
)

# ==========================================================
# Graceful interrupt handling (Ctrl+C)
# ==========================================================
# When the script is launched by double-click or "Run with PowerShell",
# Windows auto-closes the window on exit, including Ctrl+C. The trap
# below prints a clear message; the pause at the end keeps the window
# open long enough for the user to read it.

$script:SetupInterrupted = $false

# Pause-BeforeClose must be defined BEFORE the trap: PowerShell traps are
# scope-wide, but function definitions execute in order, so if an early
# statement throws, the trap must not reference a function that does not
# exist yet.
function Pause-BeforeClose($Reason = "done") {
    # Only pause if we have an interactive console; in CI / piped runs, exit.
    if ($Host.UI.RawUI -and -not $NonInteractive) {
        Write-Host ""
        switch ($Reason) {
            "cancelled" { Write-Host "Press Enter to close..." }
            "error"     { Write-Host "Press Enter to close (check the messages above)..." }
            default     { Write-Host "Press Enter to close..." }
        }
        try { $null = Read-Host } catch { Start-Sleep -Seconds 3 }
    }
}

# PowerShell's equivalent of a SIGINT trap. This is purely cosmetic Ctrl+C
# plumbing; under redirected stdio (CI, pipes, no console) touching the
# console handle throws 'The handle is invalid', so it must be guarded, or
# every -NonInteractive/automation run dies before doing any work.
try {
    [Console]::TreatControlCAsInput = $false
} catch {
    # No real console (redirected stdio). Ctrl+C handling is irrelevant here.
}
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
    # Only called on actual exit; used only to hint at the pause below
} -ErrorAction SilentlyContinue

trap {
    # Runs on any terminating error, including user-pressed Ctrl+C (in most hosts)
    $script:SetupInterrupted = $true
    Write-Host ""
    Write-Host ""
    Write-Host "! Setup cancelled or failed." -ForegroundColor Yellow
    Write-Host "  Any directories created up to this point remain in place." -ForegroundColor DarkGray
    Write-Host "  Re-run the script to resume; existing items will be skipped." -ForegroundColor DarkGray
    if ($_.Exception.Message) {
        Write-Host ""
        Write-Host "  Details: $($_.Exception.Message)" -ForegroundColor DarkGray
    }
    if (Get-Command Pause-BeforeClose -ErrorAction SilentlyContinue) {
        Pause-BeforeClose "cancelled"
    }
    exit 130
}

# ==========================================================
# Template location sanity check
# ==========================================================
# The script scaffolds into the CURRENT directory (and, with -Target,
# copies the template FROM it). If the current directory is not a cephalo
# template - e.g. the script was invoked by path from somewhere else -
# the result would be a project without agents, workflows, or templates.
# Mirrors the equivalent guard in setup.sh.

if (-not (Test-Path -LiteralPath "setup.ps1" -PathType Leaf) -or -not (Test-Path -LiteralPath ".claude" -PathType Container) -or -not (Test-Path -LiteralPath "templates" -PathType Container)) {
    $ScriptDir = $PSScriptRoot
    Write-Host ""
    Write-Host "Error: the current directory does not look like a cephalo template" -ForegroundColor Red
    Write-Host "(setup.ps1, .claude/ and templates/ expected in: $(Get-Location))." -ForegroundColor Red
    if ($ScriptDir -and (Test-Path (Join-Path $ScriptDir ".claude"))) {
        Write-Host "The template appears to be at: $ScriptDir" -ForegroundColor Yellow
        Write-Host "Run:  Set-Location `"$ScriptDir`"; .\setup.ps1 [args]" -ForegroundColor Yellow
        Write-Host "Use -Target PATH to create the project elsewhere." -ForegroundColor Yellow
    }
    exit 2
}

# ==========================================================
# Helpers
# ==========================================================

function Write-Header($Text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-Step($Text) {
    Write-Host ""
    Write-Host "-> $Text" -ForegroundColor Yellow
}

function Ask-Choice($Question, $Options) {
    Write-Host ""
    Write-Host $Question -ForegroundColor Cyan
    for ($i = 0; $i -lt $Options.Length; $i++) {
        Write-Host "  $($i+1). $($Options[$i])"
    }
    do {
        $answer = Read-Host "Choice (1-$($Options.Length))"
        if ($null -eq $answer) {
            # EOF (stdin closed, e.g. an unattended run without -NonInteractive).
            # An empty Enter returns "", not $null, and is handled below.
            Write-Host ""
            Write-Host "Error: input closed before a choice was made." -ForegroundColor Red
            Write-Host "For unattended runs, pass -WorkType, -Structure, -Scaffolding and -NonInteractive." -ForegroundColor Red
            exit 2
        }
        $n = 0
        $ok = [int]::TryParse($answer, [ref]$n)
        $valid = $ok -and $n -ge 1 -and $n -le $Options.Length
        if (-not $valid) {
            Write-Host "Please enter a number between 1 and $($Options.Length)." -ForegroundColor Yellow
        }
    } while (-not $valid)
    return $Options[$n-1]
}

function Create-DirSafe($Path) {
    if (!(Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
        Write-Host "  + $Path" -ForegroundColor Green
    } else {
        Write-Host "  . $Path (exists)" -ForegroundColor Gray
    }
}

function Create-Gitkeep($Path) {
    $kp = Join-Path $Path ".gitkeep"
    if (!(Test-Path $kp)) { New-Item -ItemType File -Path $kp -Force | Out-Null }
}

function Create-Symlink($Link, $Target) {
    if (Test-Path $Link) {
        Write-Host "  . $Link (exists)" -ForegroundColor Gray
        return
    }
    # PowerShell 5.1's New-Item resolves a RELATIVE -Target against the current
    # location, not the link's parent directory, so a relative '..\foo' target
    # is looked for one level above the project root and fails with
    # ItemNotFoundException before any privilege check. Resolve the target to an
    # absolute path anchored at the link's parent so New-Item sees a real path
    # and the only remaining failure is the genuine elevation requirement.
    $LinkParent = Split-Path $Link -Parent
    if (-not $LinkParent) { $LinkParent = "." }
    $AbsoluteTarget = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $LinkParent $Target))
    try {
        New-Item -ItemType SymbolicLink -Path $Link -Target $AbsoluteTarget -ErrorAction Stop | Out-Null
        Write-Host "  + $Link --> $Target" -ForegroundColor Green
    } catch {
        # Fallback: copy the directory contents instead of symlinking.
        # Surface the REAL exception rather than always blaming Administrator
        # rights (path-resolution, filesystem, and elevation errors all land here).
        Write-Host "  ! Symlink failed for $Link : $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "    (On Windows, real symlinks need Developer Mode or an elevated shell.)" -ForegroundColor DarkGray
        if (Test-Path $AbsoluteTarget) {
            Copy-Item -Path $AbsoluteTarget -Destination $Link -Recurse -Force
            Write-Host "    -> Copied $Target into $Link as fallback." -ForegroundColor Yellow
            Write-Host "    Note: when guidelines change, you must update each copy manually." -ForegroundColor Yellow
        } else {
            Write-Host "    Could not create $Link nor copy from $Target. Please create manually." -ForegroundColor Red
        }
    }
}

function Write-Utf8NoBom($Path, $Content) {
    # PowerShell 5.1's "Set-Content -Encoding UTF8" writes a UTF-8 BOM.
    # For cross-platform compatibility (Linux tools, Git hooks), we avoid the BOM.
    #
    # Resolve relative paths against the PowerShell provider location, NOT the
    # process working directory. Set-Location (used by the -Target flow) changes
    # only PowerShell's location; [Environment]::CurrentDirectory, which
    # [IO.Path]::GetFullPath relies on, is left pointing at the launch directory.
    # Using GetFullPath here would silently write .gitignore/.gitattributes into
    # the original template folder instead of the target project.
    $encoding = New-Object System.Text.UTF8Encoding $false
    $absolute = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
    [System.IO.File]::WriteAllText($absolute, $Content, $encoding)
}

function Copy-TemplateIfExists($Template, $Destination, $FallbackContent) {
    # Never overwrite an existing state file. Re-running setup must preserve the
    # user's accumulated 00_Status.md / 00_Decisions.md / 00_Feedback_log.md
    # (the framework's central status document and append-only decisions log),
    # mirroring Create-DirSafe's skip-if-exists behavior.
    if (Test-Path $Destination) {
        Write-Host "  . $Destination (exists, kept)" -ForegroundColor Gray
        return
    }
    if (Test-Path $Template) {
        Copy-Item $Template $Destination
        Write-Host "  + $Destination" -ForegroundColor Green
    } else {
        Write-Utf8NoBom $Destination $FallbackContent
        Write-Host "  + $Destination (minimal fallback)" -ForegroundColor Green
    }
}

function Resolve-CephaloConfiguration {
    # Normalize + validate WorkType/Structure/Scaffolding (script scope).
    # Accept both the interactive menu strings (e.g. "Flat (single directory,
    # simple)") and the documented short CLI forms (e.g. "Flat"), then reject
    # anything else. Without this, a typo like -Structure Longform (or an unset
    # value under -NonInteractive) falls through every structure branch and the
    # script prints a false "Setup complete" with an empty workflow hint and
    # wrong next-step paths.
    # Idempotent: canonical values re-validate unchanged, so it is safe to call
    # this both early (before the -Target template copy) and again after the
    # interactive prompts.

    # An empty value can only get here under -NonInteractive (the prompts fill
    # in every missing value otherwise); name the missing parameters instead of
    # reporting an "invalid" empty value.
    if ($script:WorkType -eq "" -or $script:Structure -eq "" -or $script:Scaffolding -eq "") {
        Write-Host ""
        Write-Host "Error: -NonInteractive requires -WorkType, -Structure and -Scaffolding." -ForegroundColor Red
        Write-Host "  Example: .\setup.ps1 -WorkType `"Bachelor thesis`" -Structure Long-form -Scaffolding full -NonInteractive" -ForegroundColor Red
        exit 2
    }

    $validWorkTypes = @("Seminar paper", "Presentation", "Bachelor thesis", "Master thesis", "Dissertation")
    if ($validWorkTypes -notcontains $script:WorkType) {
        Write-Host ""
        Write-Host "Error: invalid work type '$($script:WorkType)'." -ForegroundColor Red
        Write-Host "  Valid options: $($validWorkTypes -join ', ')" -ForegroundColor Red
        exit 2
    }

    # Structure: normalize to the canonical short form that every downstream
    # branch and the next-steps hint compare against.
    if ($script:Structure -match "^Flat") {
        $script:Structure = "Flat"
    } elseif ($script:Structure -match "^Long-form") {
        $script:Structure = "Long-form"
    } elseif ($script:Structure -match "^Multi-project") {
        $script:Structure = "Multi-project"
    } else {
        Write-Host ""
        Write-Host "Error: invalid structure '$($script:Structure)'." -ForegroundColor Red
        Write-Host "  Valid options: Flat, Long-form, Multi-project" -ForegroundColor Red
        exit 2
    }

    # Scaffolding: accept "Minimal...", "Standard...", and the CLI shorthand "full".
    if ($script:Scaffolding -match "^Minimal") {
        $script:Scaffolding = "Minimal"
    } elseif ($script:Scaffolding -match "^Standard" -or $script:Scaffolding -match "^(full|Full)$") {
        $script:Scaffolding = "Standard"
    } else {
        Write-Host ""
        Write-Host "Error: invalid scaffolding '$($script:Scaffolding)'." -ForegroundColor Red
        Write-Host "  Valid options: Standard (or 'full'), Minimal" -ForegroundColor Red
        exit 2
    }
}

# ==========================================================
# Start
# ==========================================================

Write-Header "cephalo setup"
Write-Host ""
Write-Host "This script prepares a project directory for academic work."
Write-Host "Current location: $(Get-Location)"
Write-Host ""
Write-Host "NOTE: The agent files (in .claude/, workflows/, etc.) and the" -ForegroundColor Gray
Write-Host "project content will coexist in this directory. Claude Code needs" -ForegroundColor Gray
Write-Host "both. This is expected and correct." -ForegroundColor Gray
Write-Host ""
Write-Host "You can cancel at any time with Ctrl+C; already-created directories" -ForegroundColor Gray
Write-Host "will stay in place and the next run will skip them." -ForegroundColor Gray
Write-Host ""

# ==========================================================
# Early validation (before any template copy)
# ==========================================================
# When all three configuration values were supplied as parameters, or under
# -NonInteractive (where nothing will prompt for a missing value), validate
# them BEFORE the -Target template copy below: a typo in -WorkType/-Structure/
# -Scaffolding must fail fast instead of leaving a stray template copy at the
# target (which would then also block the corrected non-interactive retry with
# "Refusing to copy into non-empty directory"). Mirrors setup.sh, which
# validates its positional arguments up front. Interactive runs with missing
# values are validated after the prompts instead.

if ($NonInteractive -or ($WorkType -ne "" -and $Structure -ne "" -and $Scaffolding -ne "")) {
    Resolve-CephaloConfiguration
}

# ==========================================================
# Target directory handling
# ==========================================================
# If -Target is given or the user chooses a different directory
# interactively, we copy the cephalo template to that location and
# continue the setup there. The original directory is left intact;
# at the end the user is asked whether to delete it.

$script:SourceDirBeforeMove = ""

# Interactive Target prompt
if ($Target -eq "" -and -not $NonInteractive) {
    Write-Host ""
    Write-Host "Where should the project be created?" -ForegroundColor Cyan
    Write-Host "  1. Here (current location: $(Get-Location))"
    Write-Host "  2. Choose a different directory"
    Write-Host ""
    while ($true) {
        $locChoice = Read-Host "Your choice [1-2, default 1]"
        if ([string]::IsNullOrWhiteSpace($locChoice)) { $locChoice = "1" }
        if ($locChoice -eq "1") { break }
        if ($locChoice -eq "2") {
            Write-Host ""
            Write-Host "Enter a target path. The cephalo template will be copied there,"
            Write-Host "and the project structure will be created inside it."
            Write-Host "Example: C:\Users\You\Documents\Bachelorarbeit_KMU_OSS"
            $Target = Read-Host "Target path"
            if ([string]::IsNullOrWhiteSpace($Target)) {
                Write-Host "Empty path - using current location instead." -ForegroundColor Yellow
                $Target = ""
            }
            break
        }
        Write-Host "Please enter 1 or 2."
    }
}

# Process Target if specified
if ($Target -ne "") {
    # Expand ~ manually for PowerShell (it does not do this by default)
    if ($Target.StartsWith("~")) {
        $Target = Join-Path $env:USERPROFILE $Target.Substring(1).TrimStart('\', '/')
    }
    
    # Resolve to absolute path against the PowerShell location, not the process
    # working directory that GetFullPath alone would use (see Write-Utf8NoBom)
    $Target = [System.IO.Path]::GetFullPath($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Target))
    $SourceDir = (Get-Location).Path

    if ($Target -eq $SourceDir) {
        Write-Host "Target path equals current location - proceeding here." -ForegroundColor Gray
        $Target = ""
    } elseif ($Target.TrimEnd('\','/') -eq $SourceDir.TrimEnd('\','/')) {
        Write-Host "Target path equals current location - proceeding here." -ForegroundColor Gray
        $Target = ""
    } else {
        # Refuse a target INSIDE the template directory: the copy would try to
        # copy the source into one of its own subdirectories (self-copy), fail
        # mid-way, and leave a half-populated directory behind. Reject up front
        # (case-insensitive on Windows) with an actionable message.
        $SourcePrefix = $SourceDir.TrimEnd('\','/') + [System.IO.Path]::DirectorySeparatorChar
        if ($Target.TrimEnd('\','/').StartsWith($SourcePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            Write-Host ""
            Write-Host "Error: the target directory must not be inside the cephalo template directory." -ForegroundColor Red
            Write-Host "  Template: $SourceDir" -ForegroundColor Red
            Write-Host "  Target:   $Target" -ForegroundColor Red
            Write-Host "  Choose a target outside the template folder, or run without -Target to set up here." -ForegroundColor Red
            exit 2
        }
    }
}

# ==========================================================
# Interactive prompts
# ==========================================================

if (-not $NonInteractive) {
    if ($WorkType -eq "") {
        $WorkType = Ask-Choice "What kind of work is this?" @(
            "Seminar paper",
            "Presentation",
            "Bachelor thesis",
            "Master thesis",
            "Dissertation"
        )
    }
    
    if ($Structure -eq "") {
        if ($WorkType -in @("Seminar paper", "Presentation")) {
            $Structure = "Flat"
            Write-Host ""
            Write-Host "For '$WorkType', using flat structure automatically." -ForegroundColor Gray
        } else {
            $Structure = Ask-Choice "What project structure?" @(
                "Flat (single directory, simple)",
                "Long-form (phase-based directories, centralized state)",
                "Multi-project (proposal + main work + defense, separated)"
            )
        }
    }
    
    if ($Scaffolding -eq "") {
        $Scaffolding = Ask-Choice "How much scaffolding should the script pre-create?" @(
            "Standard (full phase directories, ready to use)",
            "Minimal (only base structure; let the style-resolver add more based on your guidelines)"
        )
    }
}

# ==========================================================
# Normalize + validate configuration
# ==========================================================
# Re-validation after the interactive prompts (idempotent for values already
# canonicalized by the early-validation call above).

Resolve-CephaloConfiguration

Write-Host ""
Write-Host "Configuration:" -ForegroundColor Cyan
Write-Host "  Work type:   $WorkType" -ForegroundColor White
Write-Host "  Structure:   $Structure" -ForegroundColor White
Write-Host "  Scaffolding: $Scaffolding" -ForegroundColor White
if ($Target -ne "") { Write-Host "  Target:      $Target" -ForegroundColor White }
Write-Host ""
if ($NonInteractive) {
    Write-Host "(Non-interactive mode: proceeding without confirmation)" -ForegroundColor Gray
} else {
    $confirm = Read-Host "Proceed? (y/j = yes, n = no)"
    if ($null -eq $confirm) {
        # EOF (stdin closed): fail instead of reporting a successful "Cancelled."
        Write-Host ""
        Write-Host "Error: input closed before confirmation." -ForegroundColor Red
        Write-Host "For unattended runs, pass -WorkType, -Structure, -Scaffolding and -NonInteractive." -ForegroundColor Red
        exit 2
    }
    if ($confirm -notmatch '^(y|j|yes|ja)$') {
        Write-Host "Cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# ==========================================================
# Copy the template to -Target (after the confirmation)
# ==========================================================
# Only now, so that a declined "Proceed?" or an interrupted prompt leaves
# no template copy behind (as in setup.sh).

if ($Target -ne "") {
    $SourceDir = (Get-Location).Path
    
    # Create parent directory chain if needed
    $TargetParent = Split-Path -Parent $Target
    if ($TargetParent -and -not (Test-Path $TargetParent)) {
        Write-Host "Creating parent directory: $TargetParent" -ForegroundColor Gray
        try {
            New-Item -ItemType Directory -Path $TargetParent -Force | Out-Null
        } catch {
            Write-Host "Error: cannot create parent directory '$TargetParent'." -ForegroundColor Red
            exit 2
        }
    }
    
    # Handle existing target
    $TargetWasEmpty = $true
    if (Test-Path $Target) {
        if (Test-Path $Target -PathType Container) {
            $existing = Get-ChildItem -Path $Target -Force -ErrorAction SilentlyContinue
            if ($existing) {
                $TargetWasEmpty = $false
                Write-Host ""
                Write-Host "Warning: target directory already exists and is not empty:" -ForegroundColor Yellow
                Write-Host "  $Target" -ForegroundColor Yellow
                Write-Host ""
                if (-not $NonInteractive) {
                    $overwriteAns = Read-Host "Continue and copy into this directory? [y/N]"
                    if ($overwriteAns -notmatch '^(y|Y|j|J|yes|Yes|ja|Ja)$') {
                        Write-Host "Aborted."
                        exit 1
                    }
                } else {
                    Write-Host "Refusing to copy into non-empty directory in non-interactive mode." -ForegroundColor Red
                    exit 2
                }
            }
        } else {
            Write-Host "Error: target path exists and is not a directory." -ForegroundColor Red
            exit 2
        }
    } else {
        New-Item -ItemType Directory -Path $Target -Force | Out-Null
    }
    
    # Copy cephalo template, excluding .git and local build/runtime artifacts
    # that the repo's own .gitignore protects (__pycache__, *.pyc, venvs, and
    # Claude Code's own worktrees/local settings). These must not leak into
    # a freshly scaffolded project. The setup-wizard launcher
    # (cephalo-setup.*) is skipped too: it embeds the absolute path it was
    # generated for and would otherwise be committed with the project.
    Write-Verbose "Copying template from '$SourceDir' to target '$Target'"
    Write-Host ""
    Write-Host "Copying cephalo template to target..." -ForegroundColor Cyan
    $ExcludedTopLevelNames = @(".git", ".github", "__pycache__", ".venv", "venv")
    try {
        Get-ChildItem -Path $SourceDir -Force | Where-Object {
            $ExcludedTopLevelNames -notcontains $_.Name -and $_.Extension -ne ".pyc" -and $_.Name -notlike "cephalo-setup.*"
        } | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $Target -Recurse -Force -ErrorAction Stop
        }
    } catch {
        Write-Host "Error during copy: $($_.Exception.Message)" -ForegroundColor Red
        exit 3
    }

    # The top-level filter above only excludes matches at the copy root;
    # Copy-Item -Recurse still pulls in nested __pycache__/.venv/etc. that
    # live inside copied subdirectories (e.g. .claude\worktrees,
    # .claude\settings.local.json). Sweep those out of the target too, but
    # only if the target was empty or new: in a non-empty target the user
    # confirmed, these names may be the user's own files (e.g. a venv).
    if ($TargetWasEmpty) {
        Get-ChildItem -Path $Target -Recurse -Force -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -in @("__pycache__", ".venv", "venv") } |
            ForEach-Object { Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
        Get-ChildItem -Path $Target -Recurse -Force -File -Filter "*.pyc" -ErrorAction SilentlyContinue |
            Remove-Item -Force -ErrorAction SilentlyContinue
        $TargetClaudeWorktrees = Join-Path $Target ".claude\worktrees"
        if (Test-Path $TargetClaudeWorktrees) {
            Remove-Item -Path $TargetClaudeWorktrees -Recurse -Force -ErrorAction SilentlyContinue
        }
        $TargetClaudeLocalSettings = Join-Path $Target ".claude\settings.local.json"
        if (Test-Path $TargetClaudeLocalSettings) {
            Remove-Item -Path $TargetClaudeLocalSettings -Force -ErrorAction SilentlyContinue
        }
    }

    # Sanity check after copy
    if (-not (Test-Path (Join-Path $Target "setup.ps1")) -or -not (Test-Path (Join-Path $Target ".claude"))) {
        Write-Host "Error: copy appears incomplete. Aborting." -ForegroundColor Red
        Write-Host "  Source: $SourceDir" -ForegroundColor Red
        Write-Host "  Target: $Target" -ForegroundColor Red
        exit 3
    }
    
    Write-Host "+ Template copied to: $Target" -ForegroundColor Green
    Write-Host ""
    
    $script:SourceDirBeforeMove = $SourceDir
    Set-Location -Path $Target
    Write-Verbose "Changed PowerShell location to target: $Target"
}

$IsMinimal = $Scaffolding -match "^Minimal"
Write-Verbose "Resolved configuration: WorkType='$WorkType', Structure='$Structure', Scaffolding='$Scaffolding' (minimal=$IsMinimal)."
Write-Verbose "Working location: $((Get-Location).Path)"

# ==========================================================
# Flat structure
# ==========================================================

if ($Structure -match "^Flat") {
    Write-Verbose "Scaffolding branch: Flat"
    Write-Step "Creating flat structure"
    
    Create-DirSafe "workspace"
    Create-DirSafe "workspace\sources"
    Create-DirSafe "workspace\sources\_guidelines"
    
    if (-not $IsMinimal) {
        Create-DirSafe "workspace\sources\extracts"
        Create-DirSafe "workspace\output"
        Create-DirSafe "workspace\output\chapters"
        Create-Gitkeep "workspace\sources\extracts"
        Create-Gitkeep "workspace\output\chapters"
        
        if ($WorkType -eq "Presentation") {
            Create-DirSafe "workspace\output\slides"
            Create-DirSafe "workspace\data"
        }
        
        if ($WorkType -in @("Master thesis", "Dissertation")) {
            Create-DirSafe "workspace\methods"
            Create-DirSafe "workspace\data"
            Create-DirSafe "workspace\data\raw"
            Create-DirSafe "workspace\data\processed"
            Create-DirSafe "workspace\data\scripts"
            Create-DirSafe "workspace\data\outputs"
            Create-Gitkeep "workspace\data\raw"
            Create-Gitkeep "workspace\data\processed"
        }
    }
    
    $WorkflowHint = switch ($WorkType) {
        "Seminar paper"  { "seminar_2agent.yaml" }
        "Presentation"   { "presentation_3agent.yaml" }
        "Bachelor thesis" { "bachelor_5agent.yaml" }
        "Master thesis"  { "master_7agent.yaml" }
        "Dissertation"   { "master_7agent.yaml (adapt as needed)" }
    }
}

# ==========================================================
# Long-form structure
# ==========================================================

elseif ($Structure -match "^Long-form") {
    Write-Verbose "Scaffolding branch: Long-form"
    Write-Step "Creating long-form structure"

    Create-DirSafe "guidelines"
    
    if (-not $IsMinimal) {
        Create-DirSafe "01_Proposal"
        Create-DirSafe "02_Literature"
        Create-DirSafe "02_Literature\extracts"
        Create-DirSafe "02_Literature\sources"
        Create-DirSafe "03_Theory_chapters"
        Create-DirSafe "06_Discussion_Conclusion"
        Create-DirSafe "07_Introduction"
        Create-DirSafe "08_Formal_Review"
        Create-DirSafe "08_Formal_Review\format_reports"
        Create-DirSafe "08_Formal_Review\submissions"
        
        if ($WorkType -in @("Master thesis", "Dissertation")) {
            Create-DirSafe "04_Methods"
            Create-DirSafe "05_Empirical"
            Create-DirSafe "05_Empirical\data"
            Create-DirSafe "05_Empirical\data\raw"
            Create-DirSafe "05_Empirical\data\processed"
            Create-DirSafe "05_Empirical\data\scripts"
            Create-DirSafe "05_Empirical\data\outputs"
            Create-Gitkeep "05_Empirical\data\raw"
            Create-Gitkeep "05_Empirical\data\processed"
        }
    }
    
    # Central state files always
    Write-Step "Creating central state files"
    Copy-TemplateIfExists "templates\status.md" "00_Status.md" "# Project Status`n"
    Copy-TemplateIfExists "templates\decisions.md" "00_Decisions.md" "# Architectural Decisions`n"
    Copy-TemplateIfExists "templates\feedback_log.md" "00_Feedback_log.md" "# Feedback Log`n"
    
    if ($WorkType -in @("Master thesis", "Dissertation")) {
        $WorkflowHint = "master_7agent_longform.yaml"
    } else {
        $WorkflowHint = "bachelor_5agent_longform.yaml"
    }
}

# ==========================================================
# Multi-project structure
# ==========================================================

elseif ($Structure -match "^Multi-project") {
    Write-Verbose "Scaffolding branch: Multi-project"
    Write-Step "Creating multi-project structure"

    $MainName = "02_Main_Work"
    
    # Shared materials
    Create-DirSafe "00_Shared_Materials"
    Create-DirSafe "00_Shared_Materials\guidelines"
    Create-DirSafe "00_Shared_Materials\course_materials"
    
    # Proposal
    Create-DirSafe "01_Proposal"
    if (-not $IsMinimal) {
        Create-DirSafe "01_Proposal\01_Research"
        Create-DirSafe "01_Proposal\02_Outline"
        Create-DirSafe "01_Proposal\03_Drafting"
        Create-DirSafe "01_Proposal\04_Submission"
    }
    
    # Main work
    Create-DirSafe $MainName
    if (-not $IsMinimal) {
        Create-DirSafe "$MainName\01_Proposal_Reference"
        Create-DirSafe "$MainName\02_Literature"
        Create-DirSafe "$MainName\02_Literature\extracts"
        Create-DirSafe "$MainName\02_Literature\sources"
        Create-DirSafe "$MainName\03_Theory_chapters"
        Create-DirSafe "$MainName\06_Discussion_Conclusion"
        Create-DirSafe "$MainName\07_Introduction"
        Create-DirSafe "$MainName\08_Formal_Review"
        Create-DirSafe "$MainName\08_Formal_Review\format_reports"
        Create-DirSafe "$MainName\08_Formal_Review\submissions"
        
        if ($WorkType -in @("Master thesis", "Dissertation")) {
            Create-DirSafe "$MainName\04_Methods"
            Create-DirSafe "$MainName\05_Empirical"
            Create-DirSafe "$MainName\05_Empirical\data"
            Create-DirSafe "$MainName\05_Empirical\data\raw"
            Create-DirSafe "$MainName\05_Empirical\data\processed"
            Create-DirSafe "$MainName\05_Empirical\data\scripts"
            Create-DirSafe "$MainName\05_Empirical\data\outputs"
            Create-Gitkeep "$MainName\05_Empirical\data\raw"
        }
    }
    
    # Defense
    Create-DirSafe "03_Defense"
    if (-not $IsMinimal) {
        Create-DirSafe "03_Defense\01_Slides"
        Create-DirSafe "03_Defense\02_Speaker_Notes"
        Create-DirSafe "03_Defense\03_Defense_Prep"
        Create-DirSafe "03_Defense\04_Handout"
        Create-DirSafe "03_Defense\05_Rehearsals"
        Create-DirSafe "03_Defense\06_Defense_Day"
        Create-Gitkeep "03_Defense\04_Handout"
        Create-Gitkeep "03_Defense\05_Rehearsals"
    }
    
    # Symlinks
    Write-Step "Creating symlinks to 00_Shared_Materials"
    Create-Symlink "01_Proposal\shared" "..\00_Shared_Materials"
    Create-Symlink "$MainName\shared" "..\00_Shared_Materials"
    Create-Symlink "03_Defense\shared" "..\00_Shared_Materials"
    
    # Central files per sub-project
    Write-Step "Creating central state files per sub-project"
    foreach ($p in @("01_Proposal", $MainName, "03_Defense")) {
        Copy-TemplateIfExists "templates\status.md" "$p\00_Status.md" "# Status: $p`n"
        Copy-TemplateIfExists "templates\decisions.md" "$p\00_Decisions.md" "# Decisions: $p`n"
        Copy-TemplateIfExists "templates\feedback_log.md" "$p\00_Feedback_log.md" "# Feedback Log: $p`n"
    }
    
    $WorkflowHint = "proposal_workflow.yaml, bachelor/master_*_longform.yaml, defense_workflow.yaml (per sub-project)"
}

# ==========================================================
# Git setup (always)
# ==========================================================

Write-Verbose "Initializing Git repository and ignore/attributes files"
Write-Step "Git repository"

$GitignoreContent = @"
# System files
.DS_Store
Thumbs.db
desktop.ini

# Temporary Office files
~`$*.docx
~`$*.pptx
~`$*.xlsx
~WRL*.tmp
.~lock.*#

# Editor directories
.vscode/
.idea/
*.swp

# Python
__pycache__/
*.pyc
.venv/
venv/

# Research data — never commit it: raw data may carry personal identifiers
**/data/raw/*
**/data/processed/*

# Keep placeholders
!**/data/raw/.gitkeep
!**/data/raw/README.md
!**/data/processed/.gitkeep

# Claude Code runtime artifacts
.claude/worktrees/
.claude/settings.local.json
"@

if (!(Test-Path ".gitignore")) {
    # The here-string above inherits CRLF from this CRLF-encoded .ps1 file,
    # but the repo-root .gitignore (and most POSIX tooling) uses LF. Normalize
    # to LF and add the trailing newline the here-string omits after its last
    # line, so the generated file matches the repo-root .gitignore byte-for-byte.
    $GitignoreContentLf = ($GitignoreContent -replace "`r`n", "`n") + "`n"
    Write-Utf8NoBom ".gitignore" $GitignoreContentLf
    Write-Host "  + .gitignore" -ForegroundColor Green
} else {
    Write-Host "  . .gitignore (exists)" -ForegroundColor Gray
}

$GitattributesContent = @"
*.docx filter=lfs diff=lfs merge=lfs -text
*.pptx filter=lfs diff=lfs merge=lfs -text
*.pdf filter=lfs diff=lfs merge=lfs -text
*.xlsx filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
*.jpg filter=lfs diff=lfs merge=lfs -text
"@

# As for .gitignore: LF endings plus the trailing newline the here-string
# omits. The template ships its own .gitattributes (line-ending rules only),
# so after a -Target copy or in an in-place setup the file usually exists
# already: append the LFS rules unless it has some (no duplicates on re-run).
$GitattributesContentLf = ($GitattributesContent -replace "`r`n", "`n") + "`n"
if (!(Test-Path ".gitattributes")) {
    Write-Utf8NoBom ".gitattributes" $GitattributesContentLf
    Write-Host "  + .gitattributes" -ForegroundColor Green
} else {
    $ExistingGitattributes = [string](Get-Content -LiteralPath ".gitattributes" -Raw -Encoding UTF8)
    if ($ExistingGitattributes -notmatch "filter=lfs") {
        if ($ExistingGitattributes -and -not $ExistingGitattributes.EndsWith("`n", [System.StringComparison]::Ordinal)) {
            $ExistingGitattributes += "`n"
        }
        Write-Utf8NoBom ".gitattributes" ($ExistingGitattributes + $GitattributesContentLf)
        Write-Host "  + .gitattributes (LFS rules appended)" -ForegroundColor Green
    } else {
        Write-Host "  . .gitattributes (exists)" -ForegroundColor Gray
    }
}

if (!(Test-Path ".git")) {
    # Check git separately from git-lfs, so a missing LFS doesn't mask
    # a successful git init. Mirrors the behavior of setup.sh.
    $gitAvailable = $null -ne (Get-Command git -ErrorAction SilentlyContinue)
    if (-not $gitAvailable) {
        Write-Host "  ! Git not available. Install from https://git-scm.com" -ForegroundColor Yellow
    } else {
        try {
            git init | Out-Null
            Write-Host "  + Git repository initialized" -ForegroundColor Green
        } catch {
            Write-Host "  ! Git init failed: $($_.Exception.Message)" -ForegroundColor Yellow
        }
        
        $lfsAvailable = $null -ne (Get-Command git-lfs -ErrorAction SilentlyContinue)
        if ($lfsAvailable) {
            try {
                git lfs install | Out-Null
                Write-Host "  + Git LFS enabled" -ForegroundColor Green
            } catch {
                Write-Host "  ! Git LFS present but 'git lfs install' failed. Large files will not use LFS." -ForegroundColor Yellow
            }
        } else {
            Write-Host "  . Git LFS not available - skipping. Install from https://git-lfs.com if you expect large files." -ForegroundColor Gray
        }
    }
} else {
    Write-Host "  . Git repository exists" -ForegroundColor Gray
}

# ==========================================================
# Summary
# ==========================================================

Write-Header "Setup complete"
Write-Host ""
Write-Host "Work type:    $WorkType" -ForegroundColor White
Write-Host "Structure:    $Structure" -ForegroundColor White
Write-Host "Scaffolding:  $Scaffolding" -ForegroundColor White
Write-Host ""
Write-Host "Suggested workflow: $WorkflowHint" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
# Keep the step numbers contiguous whether or not the minimal-only step prints.
$stepNo = 1
Write-Host "$stepNo. Place institutional guidelines into:"
if ($Structure -eq "Flat") {
    Write-Host "   -> workspace\sources\_guidelines\"
} elseif ($Structure -match "Long-form") {
    Write-Host "   -> guidelines\"
} else {
    Write-Host "   -> 00_Shared_Materials\guidelines\"
}
Write-Host ""
$stepNo++
if ($Structure -match "^Multi-project") {
    Write-Host "$stepNo. Open a sub-project (e.g. 01_Proposal\) in Claude Code - not this root -"
    Write-Host "   and invoke the style-resolver:"
} else {
    Write-Host "$stepNo. Open this directory in Claude Code and invoke the style-resolver:"
}
Write-Host "   (see README.md, Quick start step 4)"
Write-Host ""

if ($IsMinimal) {
    $stepNo++
    Write-Host "$stepNo. The style-resolver will propose additional subdirectories" -ForegroundColor Yellow
    Write-Host "   based on your guidelines. Review and confirm before creation." -ForegroundColor Yellow
    Write-Host ""
}

$stepNo++
Write-Host "$stepNo. Git commit:"
Write-Host "   git add ."
Write-Host "   git commit -m 'meta: initial setup ($WorkType, $Structure)'"
Write-Host ""

# ==========================================================
# Offer to clean up the original source folder (if we copied)
# ==========================================================

if ($script:SourceDirBeforeMove -and (Test-Path $script:SourceDirBeforeMove)) {
    Write-Host "The original cephalo template folder is still at:" -ForegroundColor Gray
    Write-Host "  $($script:SourceDirBeforeMove)" -ForegroundColor Gray
    Write-Host ""
    if (-not $NonInteractive) {
        $delAns = Read-Host "Delete it now? [y/N]"
        if ($delAns -match '^(y|Y|j|J|yes|Yes|ja|Ja)$') {
            # Safety: only delete if it still looks like a cephalo template
            if ((Test-Path (Join-Path $script:SourceDirBeforeMove "setup.ps1")) -and `
                (Test-Path (Join-Path $script:SourceDirBeforeMove ".claude"))) {
                try {
                    Remove-Item -Path $script:SourceDirBeforeMove -Recurse -Force
                    Write-Host "+ Original folder deleted." -ForegroundColor Green
                } catch {
                    Write-Host "! Could not delete original folder: $($_.Exception.Message)" -ForegroundColor Yellow
                }
            } else {
                Write-Host "! Source folder no longer looks like a cephalo template." -ForegroundColor Yellow
                Write-Host "  Skipped for safety. Please review and delete manually if needed." -ForegroundColor Yellow
            }
        } else {
            Write-Host "Kept. You can delete it later manually." -ForegroundColor Gray
        }
    } else {
        Write-Host "Non-interactive run: keeping the original in place." -ForegroundColor Gray
        Write-Host "Delete manually if no longer needed:" -ForegroundColor Gray
        Write-Host "  Remove-Item -Path `"$($script:SourceDirBeforeMove)`" -Recurse -Force" -ForegroundColor Gray
    }
    Write-Host ""
}

Pause-BeforeClose "done"
