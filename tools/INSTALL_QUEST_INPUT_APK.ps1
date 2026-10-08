param([string]$ApkPath, [string]$AdbExe, [string]$Serial, [switch]$Launch)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
if (-not $ApkPath) {
    $ApkPath = Join-Path $repoRoot 'Builds\Quest_input_observation_20261008\G1QuestInputObservation.apk'
}
if (-not (Test-Path -LiteralPath $ApkPath -PathType Leaf)) { throw "APK not found: $ApkPath" }
if (-not $AdbExe) {
    $adbCommand = Get-Command adb.exe -ErrorAction SilentlyContinue
    if ($adbCommand) { $AdbExe = $adbCommand.Source }
    else {
        $candidates = @(Get-ChildItem 'C:\Program Files\Unity\Hub\Editor\*\Editor\Data\PlaybackEngines\AndroidPlayer\SDK\platform-tools\adb.exe' -ErrorAction SilentlyContinue)
        if ($candidates.Count -eq 0) { throw 'Install Unity Android Build Support (SDK/NDK) or provide -AdbExe.' }
        $AdbExe = ($candidates | Sort-Object FullName -Descending | Select-Object -First 1).FullName
    }
}
$deviceLines = @(& $AdbExe devices)
if ($LASTEXITCODE -ne 0) { throw 'ADB device listing failed.' }
$authorized = @($deviceLines | Where-Object { $_ -match '^\S+\s+device$' } | ForEach-Object { ($_ -split '\s+')[0] })
if ($Serial) {
    if ($authorized -notcontains $Serial) { throw 'Selected device is not authorized. Accept USB debugging inside Quest.' }
} else {
    if ($authorized.Count -ne 1) { throw "Expected one authorized Quest; found $($authorized.Count). Connect USB, enable developer mode and accept USB debugging. Use -Serial if several devices are connected." }
    $Serial = $authorized[0]
}
$model = (& $AdbExe -s $Serial shell getprop ro.product.model | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $model -notmatch 'Quest') { throw 'Selected ADB device is not identified as Quest; APK was not installed.' }
Write-Host 'Installing observation-only APK. No G1 connection or motor output.'
& $AdbExe -s $Serial install -r $ApkPath
if ($LASTEXITCODE -ne 0) { throw 'APK installation failed.' }
if ($Launch) {
    & $AdbExe -s $Serial shell monkey -p kr.kaeri.g1questobservation -c android.intent.category.LAUNCHER 1
    if ($LASTEXITCODE -ne 0) { throw 'APK launch failed.' }
}
