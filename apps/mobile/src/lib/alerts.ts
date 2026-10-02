import * as Application from "expo-application";
import * as BackgroundTask from "expo-background-task";
import * as Battery from "expo-battery";
import * as IntentLauncher from "expo-intent-launcher";
import * as Notifications from "expo-notifications";
import * as TaskManager from "expo-task-manager";
import { Platform } from "react-native";

import { storedCredentials } from "@/lib/session";
import { storage } from "@/lib/storage";

/**
 * Phone notifications for CareerOS alerts.
 *
 * The server scans job boards every hour and records an alert for each new match above the
 * user's threshold. Alerts reach the phone two ways:
 *
 * - Push: the server sends each alert through FCM the moment it is created, so it arrives even
 *   when the app is closed. Only builds that include Firebase can receive pushes.
 * - Checks: an OS background task (Android runs it about every 15 minutes, and much less often
 *   while it optimises the app for battery) and a check every minute while the app is open.
 *   They show the alerts a push did not deliver.
 *
 * The app's entry file (index.ts) imports this module: Android runs background tasks without
 * opening any screen, so the task must be defined as soon as the bundle loads.
 */
export const ALERT_TASK = "careeros-job-alerts";
const HANDLED_KEY = "careeros.alerts.handled";
const LEGACY_SEEN_KEY = "careeros.alerts.seen"; // a timestamp cursor, used before 0.4
const PUSH_KEY = "careeros.push";
const LAST_BACKGROUND_KEY = "careeros.alerts.lastBackground";
const CHANNEL_ID = "job-alerts";
const MAX_SHOWN = 5;
const PUSH_GRACE_MS = 3 * 60_000;
const DAY_MS = 86_400_000;
const MAX_HANDLED = 150;

interface AlertItem {
  id: string;
  type: string;
  title: string;
  body: string;
  created_at: string;
  pushed_at: string | null;
  job_id: string | null;
  data: Record<string, unknown>;
}

/** This phone's push registration. `active` is false while the server cannot send pushes. */
export interface PushState {
  token: string;
  active: boolean;
}

async function api(path: string, body?: unknown): Promise<Response | null> {
  const creds = await storedCredentials();
  if (!creds) return null;
  return fetch(`${creds.server}/api/v1${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { Authorization: `Bearer ${creds.token}`, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

/** Server times carry microseconds, which Date.parse does not always accept. */
const timeOf = (iso: string) => Date.parse(iso.replace(/(\.\d{3})\d+/, "$1"));

async function show(title: string, body: string, data: Record<string, unknown> = {}): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: { title, body, data },
    trigger: Platform.OS === "android" ? { channelId: CHANNEL_ID } : null,
  });
}

// Same shape as the push payload (notifications/push.py), so taps route the same way.
const alertData = (alert: AlertItem) => ({
  type: alert.type,
  jobId: alert.job_id,
  documentId: alert.data?.document_id ?? null,
  outreachId: alert.data?.outreach_id ?? null,
  applyKit: alert.data?.apply_kit ? "1" : "",
  view: typeof alert.data?.view === "string" ? alert.data.view : "",
});

let inFlight: Promise<number> | null = null;

/** Shows a notification for each unread alert this phone has not shown or been pushed. Returns how many. */
export async function deliverNewAlerts(options: { background?: boolean } = {}): Promise<number> {
  if (Platform.OS === "web") return 0;
  if (options.background) await storage.set(LAST_BACKGROUND_KEY, new Date().toISOString());
  // One check at a time: the background task can fire while the app is open.
  inFlight ??= checkAlerts().finally(() => {
    inFlight = null;
  });
  return inFlight;
}

/**
 * Alerts are tracked by id, not by time: with several server workers an alert can be committed a
 * moment after a newer one, and a time cursor would skip it.
 */
async function handledAlerts(alerts: AlertItem[]): Promise<string[] | null> {
  const raw = await storage.get(HANDLED_KEY);
  if (raw) {
    try {
      return JSON.parse(raw) as string[];
    } catch {
      return null;
    }
  }
  const seen = await storage.get(LEGACY_SEEN_KEY);
  if (!seen) return null;
  await storage.remove(LEGACY_SEEN_KEY);
  return alerts.filter((alert) => alert.created_at <= seen).map((alert) => alert.id);
}

async function checkAlerts(): Promise<number> {
  const response = await api("/notifications?unread_only=true&limit=50");
  if (!response?.ok) return 0;
  const alerts = ((await response.json()) as AlertItem[]).sort((a, b) => a.created_at.localeCompare(b.created_at));
  const handled = await handledAlerts(alerts);
  if (!handled) return firstCheck(alerts);

  const known = new Set(handled);
  const pushing = (await pushState())?.active ?? false;
  const now = Date.now();
  const fresh: AlertItem[] = [];
  const done: string[] = [];
  for (const alert of alerts) {
    if (known.has(alert.id)) continue;
    // Give a push a few minutes to arrive before showing the alert from here instead.
    if (pushing && !alert.pushed_at && now - timeOf(alert.created_at) < PUSH_GRACE_MS) continue;
    done.push(alert.id);
    if (!(pushing && alert.pushed_at)) fresh.push(alert); // a pushed alert is already on the phone
  }
  for (const alert of fresh.slice(-MAX_SHOWN)) await show(alert.title, alert.body, alertData(alert));
  if (fresh.length > MAX_SHOWN) {
    await show(`${fresh.length - MAX_SHOWN} more new alerts`, "Open CareerOS to see them all.");
  }
  if (done.length > 0 || handled.length === 0) {
    await storage.set(HANDLED_KEY, JSON.stringify([...handled, ...done].slice(-MAX_HANDLED)));
  }
  return fresh.length;
}

/** First check on this phone: one summary of the last day's unread alerts, not the whole backlog. */
async function firstCheck(alerts: AlertItem[]): Promise<number> {
  await storage.set(HANDLED_KEY, JSON.stringify(alerts.map((alert) => alert.id).slice(-MAX_HANDLED)));
  const recent = alerts.filter((alert) => Date.now() - timeOf(alert.created_at) < DAY_MS);
  if (recent.length === 1) await show(recent[0].title, recent[0].body, alertData(recent[0]));
  else if (recent.length > 1) {
    const latest = recent.slice(-2).reverse().map((alert) => alert.title);
    const more = recent.length > 2 ? `\nand ${recent.length - 2} more` : "";
    await show(`${recent.length} new alerts in the last day`, `${latest.join("\n")}${more}`);
  }
  return recent.length;
}

TaskManager.defineTask(ALERT_TASK, async () => {
  try {
    await deliverNewAlerts({ background: true });
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

export async function pushState(): Promise<PushState | null> {
  const raw = await storage.get(PUSH_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PushState;
  } catch {
    return null;
  }
}

/**
 * Registers this phone for instant pushes (again when the token rotates). Null when the build
 * has no Firebase: alerts then come from the background checks alone.
 */
export async function registerPush(token?: string): Promise<PushState | null> {
  if (Platform.OS !== "android") return null;
  let deviceToken = token;
  if (!deviceToken) {
    try {
      deviceToken = String((await Notifications.getDevicePushTokenAsync()).data);
    } catch {
      await storage.remove(PUSH_KEY);
      return null;
    }
  }
  const response = await api("/devices", { token: deviceToken, platform: "android" });
  if (!response?.ok) return pushState();
  const status = (await response.json()) as { push_enabled: boolean };
  const state: PushState = { token: deviceToken, active: status.push_enabled };
  await storage.set(PUSH_KEY, JSON.stringify(state));
  return state;
}

/** Stops pushes to this phone (sign-out, or phone notifications turned off). */
export async function unregisterPush(): Promise<void> {
  const state = await pushState();
  if (!state) return;
  await storage.remove(PUSH_KEY);
  await api("/devices/unregister", { token: state.token });
}

/** Whether Android optimises this app for battery, which delays background checks by hours. */
export async function backgroundRestricted(): Promise<boolean> {
  if (Platform.OS !== "android") return false;
  try {
    return await Battery.isBatteryOptimizationEnabledAsync();
  } catch {
    return false;
  }
}

/** Opens Android's "let this app always run in the background?" prompt. */
export async function allowBackground(): Promise<void> {
  try {
    await IntentLauncher.startActivityAsync(IntentLauncher.ActivityAction.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, {
      data: `package:${Application.applicationId}`,
    });
  } catch {
    await IntentLauncher.startActivityAsync(IntentLauncher.ActivityAction.IGNORE_BATTERY_OPTIMIZATION_SETTINGS);
  }
}

export interface AlertHealth {
  /** False when notifications are off for the app, or its "Job alerts" channel is muted. */
  allowed: boolean;
  push: PushState | null;
  lastBackgroundCheck: string | null;
  restricted: boolean;
  scheduled: boolean;
}

async function notificationsAllowed(): Promise<boolean> {
  if (!(await Notifications.getPermissionsAsync()).granted) return false;
  if (Platform.OS !== "android") return true;
  const channel = await Notifications.getNotificationChannelAsync(CHANNEL_ID);
  return !channel || channel.importance !== Notifications.AndroidImportance.NONE;
}

/** What Settings shows about how alerts reach this phone. */
export async function alertHealth(): Promise<AlertHealth> {
  if (Platform.OS === "web") {
    return { allowed: false, push: null, lastBackgroundCheck: null, restricted: false, scheduled: false };
  }
  const [allowed, push, lastBackgroundCheck, restricted, scheduled] = await Promise.all([
    notificationsAllowed(),
    pushState(),
    storage.get(LAST_BACKGROUND_KEY),
    backgroundRestricted(),
    TaskManager.isTaskRegisteredAsync(ALERT_TASK),
  ]);
  return { allowed, push, lastBackgroundCheck, restricted, scheduled };
}

/** A test notification: through the server when pushes are on, otherwise straight from the phone. */
export async function sendTestAlert(): Promise<"push" | "phone"> {
  if ((await pushState())?.active) {
    const response = await api("/devices/test", {});
    if (response?.ok && ((await response.json()) as { sent: number }).sent > 0) return "push";
  }
  await show("CareerOS alerts are on", "New roles that match your profile will show up like this.");
  return "phone";
}

export type AlertTarget = { kind: "job" | "document" | "email" | "apply"; id: string } | { kind: "ready" };

/** Where a tapped notification should go. */
export function alertTarget(data: Record<string, unknown> | undefined): AlertTarget | null {
  if (data?.view === "READY") return { kind: "ready" };
  const readyToApply = data?.type === "APPLICATION_READY" || data?.applyKit === "1";
  if (readyToApply && typeof data?.jobId === "string" && data.jobId) return { kind: "apply", id: data.jobId };
  if (typeof data?.outreachId === "string" && data.outreachId) return { kind: "email", id: data.outreachId };
  if (typeof data?.documentId === "string" && data.documentId) return { kind: "document", id: data.documentId };
  if (typeof data?.jobId === "string" && data.jobId) return { kind: "job", id: data.jobId };
  return null;
}
