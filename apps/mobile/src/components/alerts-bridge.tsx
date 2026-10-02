import * as Notifications from "expo-notifications";
import { useEffect } from "react";
import { Alert, AppState } from "react-native";

import {
  alertTarget,
  allowBackground,
  backgroundRestricted,
  deliverNewAlerts,
  disableAlerts,
  enableAlerts,
  registerPush,
  unregisterPush,
} from "@/lib/alerts";
import { openDocument, openEmail, openJob } from "@/lib/nav";
import { usePrefs } from "@/lib/prefs";
import { storage } from "@/lib/storage";

const FOREGROUND_POLL_MS = 60_000;
const BACKGROUND_OFFERED_KEY = "careeros.alerts.backgroundOffered";

function openTarget(response: Notifications.NotificationResponse | null) {
  const target = alertTarget(response?.notification.request.content.data as Record<string, unknown> | undefined);
  if (!target) return;
  // A notification can open the app from anywhere, so the back button just says "Back".
  if (target.kind === "email") openEmail(target.id, "Back");
  else if (target.kind === "document") openDocument(target.id, "Back");
  else openJob(target.id, "Back");
}

/** Without pushes, alerts depend on background checks, which Android delays for battery-optimised apps. */
async function offerBackgroundAccess() {
  if ((await storage.get(BACKGROUND_OFFERED_KEY)) || !(await backgroundRestricted())) return;
  await storage.set(BACKGROUND_OFFERED_KEY, "1");
  Alert.alert(
    "Get alerts on time",
    "Android is saving battery by pausing CareerOS in the background, which can delay new-match alerts by hours. Allow it to run in the background so alerts arrive within about 15 minutes.",
    [
      { text: "Not Now", style: "cancel" },
      { text: "Allow", onPress: () => void allowBackground().catch(() => undefined) },
    ],
  );
}

/** Keeps phone notifications running while signed in, and opens the job when one is tapped. */
export function AlertsBridge() {
  const { prefs } = usePrefs();
  const enabled = prefs.phoneAlerts;

  useEffect(() => {
    if (!enabled) {
      void disableAlerts().catch(() => undefined);
      void unregisterPush().catch(() => undefined);
      return;
    }
    void enableAlerts()
      .then(async (allowed) => {
        if (!allowed) return;
        const push = await registerPush().catch(() => null);
        if (!push?.active) await offerBackgroundAccess();
      })
      .catch(() => undefined);
    const tokens = Notifications.addPushTokenListener((token) => {
      void registerPush(String(token.data)).catch(() => undefined);
    });
    const check = () => void deliverNewAlerts().catch(() => undefined);
    check();
    const timer = setInterval(() => {
      if (AppState.currentState === "active") check();
    }, FOREGROUND_POLL_MS);
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") check();
    });
    return () => {
      tokens.remove();
      clearInterval(timer);
      subscription.remove();
    };
  }, [enabled]);

  useEffect(() => {
    void Notifications.getLastNotificationResponseAsync().then(openTarget).catch(() => undefined);
    const subscription = Notifications.addNotificationResponseReceivedListener(openTarget);
    return () => subscription.remove();
  }, []);

  return null;
}
