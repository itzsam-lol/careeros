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

export function openEmail(id: string, from: string) {
  router.push({ pathname: "/email/[id]", params: { id, from } });
}

/** Replies open the email, "résumé ready" alerts the document, other job alerts the job. */
export function openNotificationTarget(notification: Notification, from: string): boolean {
  const outreachId = notification.data?.outreach_id;
  if (typeof outreachId === "string" && outreachId) {
    openEmail(outreachId, from);
    return true;
  }
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
