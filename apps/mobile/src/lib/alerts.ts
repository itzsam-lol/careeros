import * as BackgroundTask from "expo-background-task";
import * as Notifications from "expo-notifications";
import * as TaskManager from "expo-task-manager";
import { Platform } from "react-native";

import { DEFAULT_SERVER } from "@/lib/auth";
import { storage } from "@/lib/storage";

/**
 * Phone notifications for new job alerts.
 *
 * The server scans job boards every hour and records an alert for each new match above the
 * user's threshold. The phone picks those up with an OS background task (Android runs it about
 * every 15 minutes, its minimum) and every minute while the app is open, and shows a system
 * notification for each alert it has not shown before. No push service is involved.
 */
export const ALERT_TASK = "careeros-job-alerts";
const SEEN_KEY = "careeros.alerts.seen";
const CHANNEL_ID = "job-alerts";
const MAX_SHOWN = 5;

interface AlertItem {
  id: string;
  title: string;
  body: string;
  created_at: string;
  job_id: string | null;
  data: Record<string, unknown>;
}

async function credentials(): Promise<{ server: string; token: string } | null> {
  const [server, raw] = await Promise.all([storage.get("careeros.server"), storage.get("careeros.session")]);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as { token: string; expiresAt: number };
    if (session.expiresAt * 1000 <= Date.now()) return null;
    return { server: (server || DEFAULT_SERVER).replace(/\/$/, ""), token: session.token };
  } catch {
    return null;
  }
}

/** Shows a notification for every unread alert newer than the last one shown. Returns how many. */
export async function deliverNewAlerts(): Promise<number> {
  if (Platform.OS === "web") return 0;
  const creds = await credentials();
  if (!creds) return 0;
  const response = await fetch(`${creds.server}/api/v1/notifications?unread_only=true&limit=30`, {
    headers: { Authorization: `Bearer ${creds.token}` },
  });
  if (!response.ok) return 0;
  const alerts = ((await response.json()) as AlertItem[]).sort((a, b) => a.created_at.localeCompare(b.created_at));
  const newest = alerts.at(-1)?.created_at;
  const seen = await storage.get(SEEN_KEY);
  if (!seen) {
    // First run on this phone: start from now instead of replaying the whole backlog.
    await storage.set(SEEN_KEY, newest ?? new Date().toISOString());
    return 0;
  }
  const fresh = alerts.filter((alert) => alert.created_at > seen);
  if (fresh.length === 0) return 0;
  const trigger = Platform.OS === "android" ? { channelId: CHANNEL_ID } : null;
  for (const alert of fresh.slice(-MAX_SHOWN)) {
    await Notifications.scheduleNotificationAsync({
      content: {
        title: alert.title,
        body: alert.body,
        data: { jobId: alert.job_id, documentId: alert.data?.document_id ?? null },
      },
      trigger,
    });
  }
  if (fresh.length > MAX_SHOWN) {
    await Notifications.scheduleNotificationAsync({
      content: { title: `${fresh.length - MAX_SHOWN} more new matches`, body: "Open CareerOS to see them all.", data: {} },
      trigger,
    });
  }
  await storage.set(SEEN_KEY, fresh.at(-1)?.created_at ?? seen);
  return fresh.length;
}

TaskManager.defineTask(ALERT_TASK, async () => {
  try {
    await deliverNewAlerts();
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/** Asks for permission and starts background checks. False if the user or the OS said no. */
export async function enableAlerts(): Promise<boolean> {
  if (Platform.OS === "web") return false;
  const permission = await Notifications.requestPermissionsAsync();
  if (!permission.granted) return false;
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync(CHANNEL_ID, {
      name: "Job alerts",
      description: "New roles that match your profile",
      importance: Notifications.AndroidImportance.HIGH,
    });
  }
  if ((await BackgroundTask.getStatusAsync()) === BackgroundTask.BackgroundTaskStatus.Restricted) return false;
  if (!(await TaskManager.isTaskRegisteredAsync(ALERT_TASK))) {
    await BackgroundTask.registerTaskAsync(ALERT_TASK, { minimumInterval: 15 });
  }
  return true;
}

export async function disableAlerts(): Promise<void> {
  if (Platform.OS === "web") return;
  if (await TaskManager.isTaskRegisteredAsync(ALERT_TASK)) {
    await BackgroundTask.unregisterTaskAsync(ALERT_TASK);
  }
}

/** Where a tapped notification should go. */
export function alertTarget(data: Record<string, unknown> | undefined): { kind: "job" | "document"; id: string } | null {
  if (typeof data?.documentId === "string" && data.documentId) return { kind: "document", id: data.documentId };
  if (typeof data?.jobId === "string" && data.jobId) return { kind: "job", id: data.jobId };
  return null;
}
