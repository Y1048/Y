[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$expectedBranch = 'main'
$expectedPolicySha256 = '463be0376c2c1f551b996d0bf9ab97833854f2cc098b9d4fea735f17ec2e9015'
$required = @(
    'README.md',
    'docs/CHAT_HANDOFF.md',
    'docs/migration/20260917/README.md',
    'START_VR_HAND_TO_MUJOCO.bat',
    'Unity_G1_VR/ProjectSettings/ProjectVersion.txt',
    'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt'
)

Push-Location $root
try {
    $inside = (& git rev-parse --is-inside-work-tree 2>$null).Trim()
    if ($inside -ne 'true') { throw 'This directory is not a Git worktree.' }

    $branch = (& git branch --show-current).Trim()
    $head = (& git rev-parse HEAD).Trim()
    $origin = (& git remote get-url origin).Trim()
    $missing = @($required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $root $_)) })
    if ($missing.Count -ne 0) {
        throw "Required source files are missing: $($missing -join ', ')"
    }

    $policy = Join-Path $root 'references/lower_body/twist2_deploy/twist2_1017_20k_torchscript.pt'
    $policySha256 = (Get-FileHash -LiteralPath $policy -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($policySha256 -ne $expectedPolicySha256) {
        throw "Policy SHA-256 mismatch: $policySha256"
    }

    $dirty = @(& git status --porcelain)
    [pscustomobject]@{
        CheckoutRoot = $root
        Branch = $branch
        ExpectedBranch = $expectedBranch
        BranchMatches = ($branch -eq $expectedBranch)
        Head = $head
        Origin = $origin
        WorkingTreeClean = ($dirty.Count -eq 0)
        PolicySha256 = $policySha256
        SourceFilesPresent = $true
        RobotOrDdsAccessPerformed = $false
    } | Format-List

    if ($branch -ne $expectedBranch) {
        throw "Expected branch '$expectedBranch', found '$branch'."
    }
    if ($dirty.Count -ne 0) {
        throw 'Checkout contains local changes; inspect git status before continuing.'
    }
    Write-Host 'DESKTOP SOURCE CHECKOUT: PASS'
}
finally {
    Pop-Location
}
