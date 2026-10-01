import { useState } from "react";
import { Alert, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, EmptyState, Field, Group, Loading, Row, T } from "@/components/ui";
import { useMe, useOpenLink } from "@/lib/api";
import { useConnectEmail, useDisconnectEmail, useEmailAccount } from "@/lib/email";
import { shortDate } from "@/lib/format";
import { useTheme } from "@/lib/theme";

const APP_PASSWORDS = "https://myaccount.google.com/apppasswords";
const TWO_STEP = "https://myaccount.google.com/signinoptions/twosv";

/** Connect the user's own Gmail so they can send outreach they approve, one email at a time. */
export default function EmailSettingsScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const account = useEmailAccount();
  const me = useMe();
  const connect = useConnectEmail();
  const disconnect = useDisconnectEmail();
  const openLink = useOpenLink();
  const refresh = useRefresh(() => account.refetch());
  const [address, setAddress] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const data = account.data;
  const showForm = data && (!data.connected || data.status === "ERROR");

  const submit = () =>
    connect.mutate(
      { address: address.trim() || data?.address || "", appPassword: password, displayName: name.trim() || me.data?.name || null },
      {
        onSuccess: () => {
          theme.haptic("success");
          setPassword("");
        },
        onError: (error) => Alert.alert("Couldn't connect", error.message),
      },
    );

  const confirmDisconnect = () =>
    Alert.alert("Disconnect Gmail?", "CareerOS forgets the app password. Drafts stay; sending needs Gmail again.", [
      { text: "Cancel", style: "cancel" },
      { text: "Disconnect", style: "destructive", onPress: () => disconnect.mutate() },
    ]);

  return (
    <Screen title="Email" back="Settings" backFallback="/settings" tabBar={false} refresh={refresh}>
      {account.isPending ? (
        <Loading />
      ) : account.isError || !data ? (
        <Card>
          <EmptyState icon="cloud-offline-outline" title="Couldn't load email settings" message={account.error?.message} />
        </Card>
      ) : (
        <>
          {data.connected ? (
            <Group
              header="Connected"
              footer={`Emails go out from your own Gmail only when you tap Send on one. Up to ${data.daily_limit} a day, to keep your address out of spam folders.`}
            >
              <Row title={data.address ?? ""} subtitle={data.display_name ? `Sends as ${data.display_name}` : undefined} icon="mail" iconColor="#EA4335" />
              <Row title="Sent in the last 24 hours" value={`${data.sent_last_24h} of ${data.daily_limit}`} />
              <Row
                title="Replies last checked"
                value={data.replies_checked_at ? shortDate(data.replies_checked_at) : "Not yet"}
              />
              <Row title="Disconnect" destructive onPress={confirmDisconnect} />
            </Group>
          ) : null}

          {data.status === "ERROR" ? (
            <Card>
              <T v="subhead" color={colors.danger}>
                {data.last_error ?? "Gmail stopped accepting the saved app password."} Create a new app password and reconnect below.
              </T>
            </Card>
          ) : null}

          {showForm ? (
            <>
              <Group header="Connect Gmail" footer="CareerOS checks the password with Gmail before saving it, stores it encrypted, and never shows it again.">
                <View style={{ padding: theme.space.lg, gap: theme.space.md }}>
                  <Field
                    label="Gmail address"
                    value={address || (data.address ?? "")}
                    onChangeText={setAddress}
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="email-address"
                    placeholder="you@gmail.com"
                  />
                  <Field
                    label="App password"
                    value={password}
                    onChangeText={setPassword}
                    autoCapitalize="none"
                    autoCorrect={false}
                    secureTextEntry
                    placeholder="16 letters from Google"
                    hint="Not your Gmail password. Create one with the steps below."
                  />
                  <Field label="Your name on emails" value={name} onChangeText={setName} placeholder={me.data?.name ?? "Your name"} />
                  <Button
                    label={connect.isPending ? "Checking with Gmail…" : "Connect"}
                    icon="link"
                    disabled={connect.isPending || password.replace(/\s/g, "").length < 8 || !(address.trim() || data.address)}
                    onPress={submit}
                  />
                </View>
              </Group>

              <Group header="Get an app password (2 minutes)">
                <Row title="1. Turn on 2-Step Verification" subtitle="Google only offers app passwords when it's on." numberOfLines={2} icon="shield-checkmark" iconColor="#34C759" chevron onPress={() => openLink(TWO_STEP)} />
                <Row title="2. Create an app password" subtitle='Name it "CareerOS" and copy the 16 letters.' numberOfLines={2} icon="key" iconColor="#FF9500" chevron onPress={() => openLink(APP_PASSWORDS)} />
                <Row title="3. Paste it above and tap Connect" icon="checkmark-circle" iconColor="#007AFF" />
              </Group>
            </>
          ) : null}
        </>
      )}
    </Screen>
  );
}
