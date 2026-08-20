@echo off
setlocal

net session >nul 2>&1
if not %errorlevel%==0 (
    echo.
    echo This fix needs administrator permission.
    echo Right-click this file and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

echo.
echo Meta Link RTX 5070 compatibility fix
echo ------------------------------------

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$files=@('C:\Program Files\Meta Horizon\Support\oculus-runtime\Compatibility.json', $env:LOCALAPPDATA + '\Oculus\Compatibility.json') | Where-Object { Test-Path -LiteralPath $_ };" ^
  "foreach($file in $files) {" ^
  "  $backup = $file + '.bak_' + (Get-Date -Format 'yyyyMMdd_HHmmss');" ^
  "  Copy-Item -LiteralPath $file -Destination $backup -Force;" ^
  "  $json = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json;" ^
  "  $list = @($json.VideoCardWhiteList);" ^
  "  $exists = $list | Where-Object { $_.Vendor -eq 'NVIDIA' -and $_.PID -eq '2D18' };" ^
  "  if(-not $exists) {" ^
  "    $entry = [pscustomobject][ordered]@{ Name='NVIDIA GeForce RTX 5070 Laptop GPU'; Vendor='NVIDIA'; PID='2D18'; SubsysVID='Any'; Comment='Local workaround for Meta Link compatibility check' };" ^
  "    $list += $entry;" ^
  "    $json.VideoCardWhiteList = $list;" ^
  "    $json | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $file -Encoding UTF8;" ^
  "    Write-Host ('Added RTX 5070 Laptop entry: ' + $file);" ^
  "  } else {" ^
  "    Write-Host ('RTX 5070 Laptop entry already exists: ' + $file);" ^
  "  }" ^
  "  Write-Host ('Backup: ' + $backup);" ^
  "}" ^
  "$key='HKCU:\Software\Microsoft\DirectX\UserGpuPreferences';" ^
  "New-Item -Path $key -Force | Out-Null;" ^
  "$gpu_paths=@('C:\Program Files\Meta Horizon\Support\oculus-runtime\OVRServer_x64.exe','C:\Program Files\Meta Horizon\Support\oculus-runtime\OVRServiceLauncher.exe','C:\Program Files\Meta Horizon\Support\oculus-runtime\OVRRedir.exe','C:\Program Files\Meta Horizon\Support\oculus-client\OculusClient.exe','C:\Program Files\Meta Horizon\Support\oculus-dash\dash\bin\OculusDash.exe','C:\Program Files\Meta Horizon\Support\oculus-librarian\OVRLibrarian.exe','C:\Program Files\Unity\Hub\Editor\6000.5.4f1\Editor\Unity.exe') | Where-Object { Test-Path -LiteralPath $_ };" ^
  "foreach($path in $gpu_paths) { New-ItemProperty -Path $key -Name $path -Value 'GpuPreference=2;' -PropertyType String -Force | Out-Null; Write-Host ('High performance GPU: ' + $path); }"

echo.
echo Restarting Meta/Oculus runtime service...
sc stop OVRService
timeout /t 4 /nobreak >nul
sc start OVRService

echo.
echo Done. Reconnect Quest Link, then check Meta Link again.
echo.
pause
