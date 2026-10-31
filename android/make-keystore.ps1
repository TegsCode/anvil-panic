# Create the release signing key for AnvilPanicClassic.apk.
#
#   powershell -ExecutionPolicy Bypass -File android\make-keystore.ps1
#
# Writes android\anvil-release.jks and android\keystore.properties, both of which
# are gitignored. KEEP THEM. Android only installs an update over an existing app
# when it is signed by the same key, so losing this file means every future build
# has to be installed as a fresh app (and nobody can update over the top).
#
# Pass -Password to choose one; otherwise a random 24-character password is made.
param(
    [string]$Password = ''
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$keytool = 'F:\dev\jdk17\bin\keytool.exe'
if (-not (Test-Path $keytool)) {
    $cmd = Get-Command keytool -ErrorAction SilentlyContinue
    if (-not $cmd) { throw 'keytool not found. Install a JDK 17 (see bootstrap-toolchain.ps1).' }
    $keytool = $cmd.Source
}

$jks = Join-Path $here 'anvil-release.jks'
$props = Join-Path $here 'keystore.properties'

if (Test-Path $jks) {
    Write-Host 'anvil-release.jks already exists - not overwriting it.'
    Write-Host 'Delete it first if you really want a new key (previous installs then cannot update).'
    if (-not (Test-Path $props)) { throw 'keystore.properties is missing; delete the .jks and re-run to regenerate both.' }
    exit 0
}

if (-not $Password) {
    $alphabet = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    $Password = -join (1..24 | ForEach-Object { $alphabet[(Get-Random -Maximum $alphabet.Length)] })
}

& $keytool -genkeypair -v `
    -keystore $jks `
    -storetype PKCS12 `
    -alias anvilpanic `
    -keyalg RSA -keysize 4096 -validity 10950 `
    -storepass $Password -keypass $Password `
    -dname 'CN=ANVIL PANIC, O=TegsCode, C=GB'

if ($LASTEXITCODE -ne 0) { throw 'keytool failed' }

@"
# Release signing for AnvilPanicClassic.apk. Keep this file and the .jks private.
storeFile=anvil-release.jks
storePassword=$Password
keyAlias=anvilpanic
keyPassword=$Password
"@ | Set-Content -Path $props -Encoding ASCII

Write-Host ''
Write-Host "Key:      $jks"
Write-Host "Password: $props"
Write-Host ''
Write-Host 'Back both files up somewhere safe. Do not commit them and do not publish them.'
