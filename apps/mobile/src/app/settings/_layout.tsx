import { Stack } from "expo-router";

import { useTheme } from "@/lib/theme";

export default function SettingsLayout() {
  const theme = useTheme();
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        animation: theme.prefs.reduceMotion ? "fade" : "default",
        contentStyle: { backgroundColor: theme.colors.background },
      }}
    />
  );
}
