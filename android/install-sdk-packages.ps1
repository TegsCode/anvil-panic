# Accept SDK licences and install the packages the APK build needs.
$ErrorActionPreference = 'Stop'
$root = 'F:\dev'
$env:JAVA_HOME = "$root\jdk17"
$env:ANDROID_HOME = "$root\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:GRADLE_USER_HOME = "$root\gradle-home"
$sdk = "$root\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat"

# sdkmanager wants one "y" per prompt, so pipe real lines, not one long string.
$answers = (1..60 | ForEach-Object { 'y' })
$answers | & $sdk --sdk_root="$root\android-sdk" --licenses | Out-Null

& $sdk --sdk_root="$root\android-sdk" --install 'platform-tools' 'platforms;android-34' 'build-tools;34.0.0'
if ($LASTEXITCODE -ne 0) { throw "sdkmanager install failed" }
Write-Host 'sdk packages installed'
& "$root\android-sdk\cmdline-tools\latest\bin\sdkmanager.bat" --sdk_root="$root\android-sdk" --list_installed
