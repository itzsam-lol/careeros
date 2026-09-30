import { Alert } from "react-native";

import { Screen } from "@/components/screen";
import { Group, Row } from "@/components/ui";
import { useLogoutEverywhere, useMe } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { shortDate } from "@/lib/format";

export default function AccountScreen() {
  const auth = useAuth();
  const me = useMe();
  const logoutAll = useLogoutEverywhere();
  const passwordAccount = me.data?.auth_provider === "password";

  const confirmSignOut = () =>
    Alert.alert("Sign Out?", "You'll need your password to sign in again.", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: () => void auth.signOut() },
    ]);

  const confirmEverywhere = () =>
    Alert.alert("Sign Out Everywhere?", "Every phone and browser signed in to this account will have to sign in again, including this one.", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out Everywhere", style: "destructive", onPress: () => logoutAll.mutate() },
    ]);

  return (
    <Screen title="Account" back="Settings" backFallback="/settings" tabBar={false}>
      <Group>
        <Row title="Name" value={me.data?.name ?? auth.session?.name ?? "—"} />
        <Row title="Email" value={me.data?.email ?? auth.session?.email ?? "—"} />
        <Row title="Member since" value={me.data ? shortDate(me.data.created_at) : "—"} />
      </Group>

      <Group header="Connection" footer="The CareerOS server this app talks to. Your session is stored in the Android keystore.">
        <Row title="Server" value={auth.server.replace(/^https?:\/\//, "")} />
        <Row title="Sign-in method" value={passwordAccount ? "Password" : (me.data?.auth_provider ?? "—")} />
      </Group>

      <Group footer={passwordAccount ? "Change your password from the web app." : undefined}>
        <Row title="Sign Out" destructive onPress={confirmSignOut} />
        {passwordAccount ? <Row title="Sign Out Everywhere" destructive onPress={confirmEverywhere} disabled={logoutAll.isPending} /> : null}
      </Group>
    </Screen>
  );
}
