# Android build

The APK is a thin shell around **the same game file** the desktop build embeds.
There is no fork of the game here: `app/src/main/assets/index.html` is a copy of
[`../play/index.html`](../play/index.html), and `build-classic.bat` in
`../desktop` embeds the very same file. Fix a bug in the game once and both
builds get it on their next build.

## What is in here

```
app/src/main/assets/index.html      the game (copied from ../play/index.html)
app/src/main/assets/overlay.js      on-screen pads, mode switch, synthetic keys
app/src/main/java/.../MainActivity.java   WebView + accelerometer + immersive mode
make-keystore.ps1                   creates the release signing key
bootstrap-toolchain.ps1             downloads JDK 17 + Android SDK + Gradle to F:\dev
install-sdk-packages.ps1            accepts licences and installs build-tools/platform 34
```

## How the controls work without touching the game

The game already listens for `ArrowLeft`, `ArrowRight` and `ShiftLeft`, and it
already handles pointer-down-and-hold, swipes and double-taps itself. So the APK
never patches the game:

- **Buttons** dispatch synthetic `KeyboardEvent`s (`repeat: true` on the hold-start
  so a held pad is not mistaken for a double-tap dash).
- **Tilt** comes from `SensorManager` in `MainActivity`, passed to
  `window.__ap.tilt(dir)`; the shell does the same key dispatch.
- **Touch** does nothing extra — that is the game's own input handling.

The mode pill in the top-right cycles `BTN → TILT → TOUCH` and the choice is
remembered in `localStorage`.

## Build

You need a JDK 17 and the Android SDK with platform 34 + build-tools 34.0.0.

```powershell
# one-time, installs everything under F:\dev
powershell -ExecutionPolicy Bypass -File android\bootstrap-toolchain.ps1
powershell -ExecutionPolicy Bypass -File android\install-sdk-packages.ps1

# one-time, creates anvil-release.jks + keystore.properties (gitignored)
powershell -ExecutionPolicy Bypass -File android\make-keystore.ps1
```

Then:

```powershell
cd android
$env:JAVA_HOME = 'F:\dev\jdk17'
$env:GRADLE_USER_HOME = 'F:\dev\gradle-home'
$env:ANDROID_HOME = 'F:\dev\android-sdk'
.\gradlew.bat assembleRelease
```

The signed APK lands at `app/build/outputs/apk/release/app-release.apk`. Without
`keystore.properties` the same command still builds, but the output is unsigned
and Android will refuse to install it.

Check the result:

```powershell
& 'F:\dev\android-sdk\build-tools\34.0.0\aapt2.exe' dump badging app\build\outputs\apk\release\app-release.apk
& 'F:\dev\android-sdk\build-tools\34.0.0\apksigner.bat' verify --print-certs app\build\outputs\apk\release\app-release.apk
```

## Things that are deliberate

- **No `INTERNET` permission.** The game is one local file. There is no analytics,
  no ads and no way for the app to phone home. Adding the permission would make
  that a lie.
- **`sensorLandscape`.** The game is wide; portrait would letterbox it into a
  postage stamp. `configChanges` keeps the activity alive through rotation so a
  turn does not restart the run.
- **`noCompress 'html'`.** The game is stored uncompressed in the APK so the
  WebView can map it straight out of the archive instead of inflating 54 KB on
  every launch.
- **No AndroidX.** One activity, one WebView, `minSdk 26`. Adding AppCompat would
  multiply the APK size for nothing.
- **Immutable signing key.** `anvil-release.jks` is gitignored on purpose. Keep a
  backup: without it, a new build cannot install over an old one.
