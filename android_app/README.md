# Halo Scan — Android app

A native Android app (APK) for Halo Scan. It shows the same role-based web app the server
serves to browsers (`web_app/`), and adds:

- **Camera capture**: "Upload" offers *Take a photo*, *Record a 10-second video* or *Choose an
  existing file*. Captures stay in the app's private cache and are deleted on the next capture
  and when the app closes; they never go to the phone's gallery.
- **Printing**: "Print / save PDF report" opens Android printing (which includes *Save as PDF*).
- **Connection screen**: asks once for the server address and checks it really is a Halo Scan
  server; if the server becomes unreachable it offers *Try again* or *Change server address*.

The analysis itself still runs on the computer: the phone is a client of the Halo Scan server.

## Using it

1. On the computer, start the server so other devices on the network can reach it:
   ```
   cd backend
   .venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
   ```
   Allow Python through Windows Firewall when asked (private networks).
2. Find the computer's Wi-Fi address: `ipconfig` → *Wireless LAN adapter Wi-Fi* → *IPv4 Address*.
3. Connect the phone to the **same Wi-Fi**, install the APK, open Halo Scan and enter
   `http://<that address>:8001`, e.g. `http://192.168.1.20:8001`.

The live camera preview inside the page needs HTTPS, so over plain Wi-Fi **Start camera** opens
the phone's own camera instead: a photo in the *Photo* tab, a 10-second recording in the *Video*
tab. The result goes straight back into the page, ready to analyse.

## Building

Requires JDK 17+ and the Android SDK with platform 36 and build-tools 37.0.0 (set the SDK
location in `local.properties` or `ANDROID_HOME`). From this folder:
```
gradle assembleDebug        # or ./gradlew assembleDebug
```
The APK is written to `app/build/outputs/apk/debug/app-debug.apk`. A debug APK is signed with
a development key: fine for installing on your own phones, not for the Play Store.
