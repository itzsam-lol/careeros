# Android app

The app lives in `apps/mobile` (Expo SDK 57, React Native 0.86, expo-router). It talks to the
CareerOS API over HTTPS; the default server is baked in at build time from
`EXPO_PUBLIC_API_BASE_URL` and can be changed on the sign-in screen.

## Features

Tabs: **Today**, **Jobs**, **Tracker**, **Résumés** and **Profile**. Alerts open from the bell on
Today and Settings from the gear on Profile.

- **Today**: stats, notification stack, top matches, deadlines and agent activity. Sections can be
  reordered and hidden.
- **Jobs**: views, search and sort, save/dismiss/restore, and a full match explanation with
  evidence. Each job page also has:
  - application tracking (stage, follow-up reminder, notes)
  - a tailored résumé and a cover letter (professional, warm or concise)
  - interview prep and editable message drafts
- **Tracker**: the application pipeline by stage, with overdue follow-ups highlighted.
- **Résumés**: the master LaTeX résumé (view the PDF, replace the `.tex` file, see which sections
  get tailored) and every generated résumé or letter. Each one shows its skill coverage, what
  changed and why, and has open, share and star actions.
- **Profile**: a review queue for verifying or rejecting imported facts.
- **Settings**
  - On-device preferences:
    - Appearance: accent, background, card style, corners, text size, bold text, font, density.
    - Navigation and motion: tab labels, reduced motion, haptics.
    - Jobs: list filters and card details.
    - Data: refresh interval.
  - Server settings:
    - Alert thresholds.
    - Job-search preferences: roles, locations, exclusions, pay, work style, and
      sponsorship-only countries.
  - Job sources: add, schedule, run, disable, delete, and **Browse Companies** (136 verified boards
    for India and Australia).

## Building a release APK (Windows)

Requirements: Android SDK, JDK 17, Node ≥ 20.19.4 (portable copies work; nothing needs to be
installed system-wide).

```bash
cd apps/mobile
export JAVA_HOME=C:/path/to/jdk-17 ANDROID_HOME=$LOCALAPPDATA/Android/Sdk
export EXPO_PUBLIC_API_BASE_URL=https://<your-api-host>:8443
npx expo prebuild --platform android --clean --no-install
# release signing: add a `release` signingConfig that reads CAREEROS_UPLOAD_* gradle properties
cd android && ./gradlew assembleRelease
# -> android/app/build/outputs/apk/release/app-release.apk
```

Notes:

- Build from the real checkout path, not a `subst` drive. React Native codegen fails when Node and
  Gradle see different drive roots.
- `android/` is generated and git-ignored. Keep the release keystore safe: Android only installs
  updates signed with the same key.
- The workspace uses `node-linker=hoisted` (see `.npmrc`) because Metro and Gradle expect a flat
  `node_modules` layout.
