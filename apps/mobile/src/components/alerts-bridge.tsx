import * as Notifications from "expo-notifications";
import { useEffect } from "react";
import { AppState } from "react-native";

import { alertTarget, deliverNewAlerts, disableAlerts, enableAlerts } from "@/lib/alerts";
import { openDocument, openJob } from "@/lib/nav";
import { usePrefs } from "@/lib/prefs";

const FOREGROUND_POLL_MS = 60_000;

function openTarget(response: Notifications.NotificationResponse | null) {
  const target = alertTarget(response?.notification.request.content.data as Record<string, unknown> | undefined);
  if (!target) return;
  if (target.kind === "document") openDocument(target.id, "Alerts");
  else openJob(target.id, "Alerts");
}

/** Keeps phone notifications running while signed in, and opens the job when one is tapped. */
export function AlertsBridge() {
  const { prefs } = usePrefs();
  const enabled = prefs.phoneAlerts;

  useEffect(() => {
    if (!enabled) {
      void disableAlerts();
      return;
    }
    void enableAlerts().catch(() => undefined);
    const check = () => void deliverNewAlerts().catch(() => undefined);
    check();
    const timer = setInterval(() => {
      if (AppState.currentState === "active") check();
    }, FOREGROUND_POLL_MS);
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") check();
    });
    return () => {
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
