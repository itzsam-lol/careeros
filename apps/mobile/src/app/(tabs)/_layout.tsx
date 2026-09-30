import { router, Tabs } from "expo-router";
import { useEffect, useRef } from "react";

import { AppTabBar } from "@/components/tab-bar";
import { START_TABS } from "@/lib/prefs";
import { useTheme } from "@/lib/theme";

export default function TabsLayout() {
  const theme = useTheme();
  const startTab = theme.prefs.startTab;
  const opened = useRef(false);

  // Honour the "Open app on" preference once per launch.
  useEffect(() => {
    if (opened.current) return;
    opened.current = true;
    if (startTab !== "index" && START_TABS.includes(startTab)) router.navigate(`/${startTab}`);
  }, [startTab]);

  return (
    <Tabs
      tabBar={(props) => <AppTabBar {...props} />}
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: theme.colors.background },
        animation: theme.prefs.reduceMotion ? "none" : "fade",
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Today" }} />
      <Tabs.Screen name="jobs" options={{ title: "Jobs" }} />
      <Tabs.Screen name="tracker" options={{ title: "Tracker" }} />
      <Tabs.Screen name="resumes" options={{ title: "Résumés" }} />
      <Tabs.Screen name="profile" options={{ title: "Profile" }} />
    </Tabs>
  );
}
