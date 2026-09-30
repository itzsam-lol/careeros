import { router } from "expo-router";

import type { Notification } from "@/lib/api";

// Pushed screens get the name of the screen they came from, so the back button reads
// "‹ Today" or "‹ Job" like a UINavigationBar instead of a fixed label.

export function openJob(id: string, from: string) {
  router.push({ pathname: "/job/[id]", params: { id, from } });
}

export function openDocument(id: string, from: string) {
  router.push({ pathname: "/resume/[id]", params: { id, from } });
}

/** "Résumé ready" alerts open the document; other job alerts open the job. False if neither. */
export function openNotificationTarget(notification: Notification, from: string): boolean {
  const documentId = notification.data?.document_id;
  if (typeof documentId === "string" && documentId) {
    openDocument(documentId, from);
    return true;
  }
  if (notification.job_id) {
    openJob(notification.job_id, from);
    return true;
  }
  return false;
}
