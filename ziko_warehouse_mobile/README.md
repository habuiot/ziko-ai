# ZIKO Warehouse / Android native display shell 1.7.0

This is the **previously built** Android source of the independently signed APK, not a new deployment. The app points to the user's single self-hosted Warehouse instance in Proxmox CT103. Inventory, users, password verification and photos are stored on the server, never in a second app database.

- Android minSdk 29, targetSdk 35; app ID `hu.ziko.warehouse`.
- Same-origin WebView, DOM storage and session cookies; in-app URL picker restricted to HTTPS or private local HTTP/VPN hosts.
- Local HTTP is not encrypted, including passwords. Use a trusted private HTTPS endpoint when available; **never publish the local HTTP backend on the internet**.
- Camera/system file chooser, CSV DownloadManager, retry, connectivity status and refresh.
- Server web UI changes appear on reload without an app update; native Android code changes require a newly signed APK with increased versionCode.
- Signed APK SHA256: `056f85867e87200a0f0cb8048e28c0c5372a73099d0870ae9c333c514ad5a437` (Warehouse backend distribution route v1.7.1).
- **Signing keys/passwords are NOT stored in this repository.** Original private signing identity resides on the user's Proxmox host; required to distribute update-compatible signed APKs.
- Original bundle and signed APK in ZIKO Release Vault `ziko-warehouse/r000002-20261117T134153Z` (verify PASS).
- Warehouse mobile Knowledge `de0f3188-6332-4142-a85a-3602d30c7ad2`, Work Hub `warehouse-2126`, ZikoTodo `WH-MOB01`.

For Linux build, run `./build.sh` with `ANDROID_SDK_ROOT` set to an Android SDK containing `platforms/android-35` and `build-tools/36.0.0`, and `JAVA_HOME` pointing to JDK 21. Without the owner's private key the script only produces an unsigned QA APK; do **not** attempt to install or distribute an unsigned APK as a release.

No physical Android/iPhone end-to-end test has been completed.
