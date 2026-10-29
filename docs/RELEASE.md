# Building the APK and AAB

The app is built by GitHub Actions, because building Android needs a JDK, the
Android SDK and Gradle — a full toolchain that a plain server does not have.
Every push to `main` builds both artefacts automatically:

1. Open the **Actions** tab of the repository.
2. Click the newest **Build APK and AAB** run.
3. Download **media-studio-debug-apk** (installable on any phone) or
   **media-studio-release-aab** (upload to Play Console).

## What you get

| Artefact | Use | Signed? |
|---|---|---|
| `app-debug.apk` | Install directly on a phone for testing | Yes, with the debug key |
| `app-release.aab` | Upload to Google Play Console | No — Play signs it for you |

A debug APK installs on any Android phone: allow "install from unknown sources"
and tap the file. It is fine for testing with your team; it is not for public
release, because debug builds are larger and the debug key is not secret.

## Building locally, if you have Android Studio

```bash
cd android
gradle assembleDebug      # -> app/build/outputs/apk/debug/app-debug.apk
gradle bundleRelease      # -> app/build/outputs/bundle/release/app-release.aab
```

Open the folder in Android Studio instead of running Gradle directly if you want
the IDE to generate the wrapper. Set `MEDIA_API_BASE_URL` in
`android/gradle.properties` before building — the app bakes it in at build time,
so point it at your deployed backend, not localhost.

## Signing a release build properly

1. Create a keystore once and keep it safe:
   ```bash
   keytool -genkey -v -keystore media-studio.jks -keyalg RSA \
           -keysize 2048 -validity 10000 -alias media-studio
   ```
2. Add four repository secrets: `KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`,
   `KEY_ALIAS`, `KEY_PASSWORD` (`KEYSTORE_BASE64` is
   `base64 -w0 media-studio.jks`).
3. Add a signing config to `android/app/build.gradle.kts` reading those secrets
   from environment variables in CI.

Until then, the release AAB is unsigned and Play Console will sign it with an
upload key when you first upload — which is the normal Play App Signing flow and
needs no keystore in CI.

## Why the build is not done in the assistant sandbox

The sandbox has Python and ffmpeg but no JDK and no Android SDK, so it cannot
produce an APK. Rather than pretend, the build is delegated to GitHub Actions,
which has the toolchain and produces the artefacts in about five minutes.
