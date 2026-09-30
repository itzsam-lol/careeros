import Ionicons from "@expo/vector-icons/Ionicons";
import { useQuery } from "@tanstack/react-query";
import { Image } from "expo-image";
import { useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, type TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Button, Card, Field, T } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { DEFAULT_SERVER, normalizeServer, probeServer, useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";

function hostOf(server: string): string {
  return server.replace(/^https?:\/\//, "");
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "validation_failed") return "Enter your email address and password.";
    return error.message;
  }
  if (error instanceof Error) {
    if (/network request failed|failed to fetch|load failed/i.test(error.message)) {
      return "Couldn't reach the server. Check the address and your internet connection.";
    }
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export default function LoginScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const insets = useSafeAreaInsets();
  const auth = useAuth();
  const initialServer = auth.server || DEFAULT_SERVER;
  const [committed, setCommitted] = useState<string | null>(initialServer || null);
  const [draft, setDraft] = useState(initialServer);
  const [email, setEmail] = useState(auth.session?.email ?? "");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const passwordRef = useRef<TextInput>(null);

  const config = useQuery({
    queryKey: ["auth-config", committed],
    queryFn: () => probeServer(committed ?? ""),
    enabled: !!committed,
    retry: 1,
  });

  const connect = () => {
    const next = normalizeServer(draft);
    if (!next) return;
    setError(null);
    setCommitted(next);
  };

  const submit = async () => {
    if (!committed) return;
    setBusy(true);
    setError(null);
    try {
      if (config.data?.mode === "dev") await auth.signInDev(committed);
      else await auth.signIn(committed, email, password);
      theme.haptic("success");
    } catch (err) {
      theme.haptic("warning");
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const mode = config.data?.mode;
  const canSubmit = mode === "dev" || (email.trim().length > 3 && password.length > 0);

  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={[styles.content, { paddingTop: insets.top + 56, paddingBottom: insets.bottom + 24, gap: theme.space.xl }]}
        >
          <View style={styles.brand}>
            <Image source={require("@/assets/images/icon.png")} style={styles.icon} contentFit="cover" accessibilityIgnoresInvertColors />
            <T v="largeTitle">CareerOS</T>
            <T v="body" color={colors.text2} style={{ textAlign: "center" }}>
              Your personal career agent. It finds the roles worth your time and never acts without you.
            </T>
          </View>

          {!committed ? (
            <Card>
              <View style={{ gap: theme.space.lg }}>
                <Field
                  label="Server address"
                  value={draft}
                  onChangeText={setDraft}
                  placeholder="careeros.example.com"
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="url"
                  returnKeyType="go"
                  onSubmitEditing={connect}
                  hint="The address of your CareerOS server."
                />
                <Button label="Continue" onPress={connect} disabled={!draft.trim()} />
              </View>
            </Card>
          ) : (
            <View style={{ gap: theme.space.lg }}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={`Server ${hostOf(committed)}. Change server`}
                onPress={() => {
                  setDraft(committed);
                  setCommitted(null);
                  setError(null);
                }}
                style={[styles.server, { backgroundColor: colors.fill, borderRadius: theme.radius.pill }]}
              >
                <View style={[styles.dot, { backgroundColor: config.isError ? "#FF3B30" : config.data ? "#34C759" : "#FF9500" }]} />
                <T v="footnote" color={colors.text2} numberOfLines={1} style={{ flexShrink: 1 }}>
                  {hostOf(committed)}
                </T>
                <T v="footnote" color={theme.accent}>
                  Change
                </T>
              </Pressable>

              {config.isPending ? (
                <T v="body" color={colors.text2} style={{ textAlign: "center" }}>
                  Connecting…
                </T>
              ) : config.isError ? (
                <Card>
                  <View style={{ gap: theme.space.md, alignItems: "center" }}>
                    <Ionicons name="cloud-offline-outline" size={32} color={colors.text3} />
                    <T v="body" color={colors.text2} style={{ textAlign: "center" }}>
                      {errorText(config.error)}
                    </T>
                    <Button label="Try Again" variant="tinted" size="medium" onPress={() => void config.refetch()} />
                  </View>
                </Card>
              ) : mode === "firebase" ? (
                <Card>
                  <T v="body" color={colors.text2}>
                    This server uses Google sign-in, which the Android app doesn't support yet. Use the web app instead.
                  </T>
                </Card>
              ) : (
                <>
                  {mode === "password" ? (
                    <Card>
                      <View style={{ gap: theme.space.lg }}>
                        <Field
                          label="Email"
                          value={email}
                          onChangeText={setEmail}
                          placeholder="you@example.com"
                          autoCapitalize="none"
                          autoCorrect={false}
                          autoComplete="email"
                          keyboardType="email-address"
                          textContentType="username"
                          returnKeyType="next"
                          onSubmitEditing={() => passwordRef.current?.focus()}
                        />
                        <Field
                          ref={passwordRef}
                          label="Password"
                          value={password}
                          onChangeText={setPassword}
                          placeholder="Required"
                          secureTextEntry
                          autoComplete="current-password"
                          textContentType="password"
                          returnKeyType="go"
                          onSubmitEditing={() => canSubmit && void submit()}
                        />
                      </View>
                    </Card>
                  ) : (
                    <T v="body" color={colors.text2} style={{ textAlign: "center" }}>
                      This is a development server. You'll be signed in as the local developer account.
                    </T>
                  )}
                  {error ? (
                    <T v="subhead" color={colors.danger} style={{ textAlign: "center" }}>
                      {error}
                    </T>
                  ) : null}
                  <Button label={mode === "dev" ? "Continue" : "Sign In"} onPress={() => void submit()} loading={busy} disabled={!canSubmit} />
                </>
              )}
            </View>
          )}

          <View style={styles.footer}>
            <Ionicons name="lock-closed" size={12} color={colors.text3} />
            <T v="caption" color={colors.text2}>
              Your session is stored securely on this device.
            </T>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  content: { flexGrow: 1, paddingHorizontal: 24 },
  brand: { alignItems: "center", gap: 8, paddingHorizontal: 8 },
  icon: { width: 88, height: 88, borderRadius: 20, marginBottom: 12 },
  server: { flexDirection: "row", alignItems: "center", gap: 8, alignSelf: "center", paddingHorizontal: 14, paddingVertical: 8, maxWidth: "100%" },
  dot: { width: 8, height: 8, borderRadius: 4 },
  footer: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 6, marginTop: "auto" },
});
