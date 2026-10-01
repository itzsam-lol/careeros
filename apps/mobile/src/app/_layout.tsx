import { Inter_400Regular } from "@expo-google-fonts/inter/400Regular";
import { Inter_500Medium } from "@expo-google-fonts/inter/500Medium";
import { Inter_600SemiBold } from "@expo-google-fonts/inter/600SemiBold";
import { Inter_700Bold } from "@expo-google-fonts/inter/700Bold";
import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useFonts } from "expo-font";
import { DefaultTheme, Stack, ThemeProvider } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useCallback, useEffect, useState } from "react";
import { AppState } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";

import { AlertsBridge } from "@/components/alerts-bridge";
import { ApiError } from "@/lib/api";
import { AuthProvider, useAuth } from "@/lib/auth";
import { PrefsProvider, usePrefs } from "@/lib/prefs";
import { useTheme } from "@/lib/theme";

void SplashScreen.preventAutoHideAsync();

// Refetch stale queries when the app returns to the foreground.
focusManager.setEventListener((setFocused) => {
  const subscription = AppState.addEventListener("change", (state) => setFocused(state === "active"));
  return () => subscription.remove();
});

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        // Retry network hiccups, never auth or validation failures.
        retry: (failures, error) => !(error instanceof ApiError && error.status < 500) && failures < 2,
      },
      mutations: { retry: false },
    },
  });
}

function RootNavigator({ fontsReady }: { fontsReady: boolean }) {
  const { status } = useAuth();
  const { ready: prefsReady } = usePrefs();
  const theme = useTheme();
  const ready = status !== "loading" && prefsReady && fontsReady;

  useEffect(() => {
    if (ready) void SplashScreen.hideAsync();
  }, [ready]);

  if (!ready) return null;
  const signedIn = status === "signed-in";
  const animation = theme.prefs.reduceMotion ? "fade" : "default";

  return (
    <ThemeProvider
      value={{
        ...DefaultTheme,
        colors: {
          ...DefaultTheme.colors,
          background: theme.colors.background,
          card: theme.colors.card,
          primary: theme.accent,
          text: theme.colors.text,
          border: theme.colors.separator,
        },
      }}
    >
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: false, animation, contentStyle: { backgroundColor: theme.colors.background } }}>
        <Stack.Protected guard={signedIn}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="job/[id]" />
          <Stack.Screen name="alerts" />
          <Stack.Screen name="resume/[id]" />
          <Stack.Screen name="prep/[id]" />
          <Stack.Screen name="outreach/[id]" />
          <Stack.Screen name="company/[id]" />
          <Stack.Screen name="apply/[id]" />
          <Stack.Screen name="email/[id]" />
          <Stack.Screen name="settings" />
        </Stack.Protected>
        <Stack.Protected guard={!signedIn}>
          <Stack.Screen name="login" options={{ animation: "fade" }} />
        </Stack.Protected>
      </Stack>
      {signedIn ? <AlertsBridge /> : null}
    </ThemeProvider>
  );
}

export default function RootLayout() {
  const [queryClient] = useState(makeQueryClient);
  const [fontsLoaded, fontError] = useFonts({ Inter_400Regular, Inter_500Medium, Inter_600SemiBold, Inter_700Bold });
  // Drop every cached response on sign-out so nothing leaks into the next session.
  const clearCache = useCallback(() => queryClient.clear(), [queryClient]);
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <QueryClientProvider client={queryClient}>
        <PrefsProvider>
          <AuthProvider onSignOut={clearCache}>
            {/* A font that fails to load falls back to the system font rather than blocking the app. */}
            <RootNavigator fontsReady={fontsLoaded || !!fontError} />
          </AuthProvider>
        </PrefsProvider>
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}
