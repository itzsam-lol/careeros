import { type Schema, unwrap } from "@careeros/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "@/lib/api";

export type EmailAccount = Schema<"EmailAccountOut">;
export type OutreachEmail = Schema<"MessageOut">;
export type EmailKind = Schema<"MessageIn">["kind"];

export const EMAIL_KINDS: readonly string[] = ["referral_request", "follow_up", "thank_you"];

export function useEmailAccount() {
  const api = useApi();
  return useQuery({ queryKey: ["email-account"], queryFn: () => unwrap(api.GET("/api/v1/email/account")) });
}

export function useConnectEmail() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { address: string; appPassword: string; displayName: string | null }) =>
      unwrap(
        api.PUT("/api/v1/email/account", {
          body: { address: input.address, app_password: input.appPassword, display_name: input.displayName },
        }),
      ),
    onSuccess: (account) => queryClient.setQueryData(["email-account"], account),
  });
}

export function useDisconnectEmail() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/email/account");
      if (error || !response.ok) throw new Error("Couldn't disconnect");
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["email-account"] }),
  });
}

export function useEmails(jobId?: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["emails", jobId ?? "all"],
    queryFn: () => unwrap(api.GET("/api/v1/email/messages", { params: { query: { job_id: jobId, limit: 100 } } })),
  });
}

export function useEmail(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["email", id],
    queryFn: () => unwrap(api.GET("/api/v1/email/messages/{message_id}", { params: { path: { message_id: id } } })),
  });
}

export function useCreateEmail() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Schema<"MessageIn">) => unwrap(api.POST("/api/v1/email/messages", { body })),
    onSuccess: (email) => {
      queryClient.setQueryData(["email", email.id], email);
      void queryClient.invalidateQueries({ queryKey: ["emails"] });
    },
  });
}

export function useEmailActions(id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  const settle = (email: OutreachEmail) => {
    queryClient.setQueryData(["email", id], email);
    void queryClient.invalidateQueries({ queryKey: ["emails"] });
    void queryClient.invalidateQueries({ queryKey: ["email-account"] });
  };
  const save = useMutation({
    mutationFn: (patch: Schema<"MessagePatch">) =>
      unwrap(api.PATCH("/api/v1/email/messages/{message_id}", { params: { path: { message_id: id } }, body: patch })),
    onSuccess: settle,
  });
  const send = useMutation({
    // Only called after the user has reviewed the final email and confirmed in a dialog.
    mutationFn: () =>
      unwrap(api.POST("/api/v1/email/messages/{message_id}/send", { params: { path: { message_id: id } }, body: { confirm: true } })),
    onSuccess: settle,
    onError: () => void queryClient.invalidateQueries({ queryKey: ["email", id] }),
  });
  const remove = useMutation({
    mutationFn: async () => {
      const { error, response } = await api.DELETE("/api/v1/email/messages/{message_id}", { params: { path: { message_id: id } } });
      if (error || !response.ok) throw new Error("Couldn't delete the draft");
    },
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["emails"] }),
  });
  return { save, send, remove };
}

export function useCheckReplies() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/email/check-replies")),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["emails"] });
      void queryClient.invalidateQueries({ queryKey: ["email"] });
    },
  });
}

export function emailStatus(email: OutreachEmail): { label: string; tone: "neutral" | "accent" | "good" | "bad" | "warn" } {
  if (email.reply_received_at) return { label: "Replied", tone: "good" };
  switch (email.status) {
    case "SENT":
      return { label: "Sent", tone: "accent" };
    case "SENDING":
      return { label: "Sending", tone: "warn" };
    case "FAILED":
      return { label: "Not sent", tone: "bad" };
    default:
      return { label: "Draft", tone: "neutral" };
  }
}
