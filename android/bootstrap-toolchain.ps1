# Android build toolchain for the ANVIL PANIC APK.
# Everything lands on F: because C: has ~2 GB free.
$ErrorActionPreference = 'Stop'
$root = 'F:\dev'
New-Item -ItemType Directory -Force -Path $root, "$root\dl", "$root\gradle-home" | Out-Null

function Get-Zip($url, $out) {
  if (Test-Path $out) { Write-Host "have $out"; return }
  Write-Host "downloading $url"
  # curl.exe ships with Windows and is far faster than Invoke-WebRequest here
  & curl.exe -L --fail --retry 3 -o $out $url
  if ($LASTEXITCODE -ne 0) { throw "download failed: $url" }
}

# 1. JDK 17 (Temurin, no installer)
Get-Zip 'https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse' "$root\dl\jdk17.zip"
if (-not (Test-Path "$root\jdk17")) {
  Expand-Archive "$root\dl\jdk17.zip" -DestinationPath "$root\jdk17-tmp" -Force
  $inner = Get-ChildItem "$root\jdk17-tmp" -Directory | Select-Object -First 1
  Move-Item $inner.FullName "$root\jdk17"
  Remove-Item "$root\jdk17-tmp" -Recurse -Force
}
Write-Host "jdk: $root\jdk17"

# 2. Android command line tools
Get-Zip 'https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip' "$root\dl\cmdline-tools.zip"
if (-not (Test-Path "$root\android-sdk\cmdline-tools\latest")) {
  Expand-Archive "$root\dl\cmdline-tools.zip" -DestinationPath "$root\dl\cmdline" -Force
  New-Item -ItemType Directory -Force -Path "$root\android-sdk\cmdline-tools" | Out-Null
  Move-Item "$root\dl\cmdline\cmdline-tools" "$root\android-sdk\cmdline-tools\latest"
}

# 3. Gradle
Get-Zip 'https://services.gradle.org/distributions/gradle-8.7-bin.zip' "$root\dl\gradle.zip"
if (-not (Test-Path "$root\gradle-8.7")) {
  Expand-Archive "$root\dl\gradle.zip" -DestinationPath $root -Force
}

# 4. SDK packages
$env:JAVA_HOME = "$root\jdk17"
$env:ANDROID_HOME = "$root\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:GRADLE_USER_HOME = "$root\gradle-home"
$env:Path = "$env:JAVA_HOME\bin;$env:JAVA_HOME\bin;$root\gradle-8.7\bin;" + $env:Path

$sdk = "$root\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat"
Write-Host "accepting licences"
'y' * 40 | & $sdk --sdk_root="$root\android-sdk" --licenses | Out-Null
& $sdk --sdk_root="$root\android-sdk" 'platform-tools' 'platforms;android-34' 'build-tools;34.0.0'
Write-Host 'toolchain ready'
