import Ionicons from "@expo/vector-icons/Ionicons";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, FlatList, Pressable, ScrollView, StyleSheet, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { JobCardView, useJobFilter } from "@/components/job-card";
import { TAB_BAR_SPACE, useRefresh, useRefreshControl } from "@/components/screen";
import { Button, Card, EmptyState, Segmented, T } from "@/components/ui";
import { type JobSort, type JobView, useJobs } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { useTheme } from "@/lib/theme";

export const JOB_VIEWS: { value: JobView; label: string; empty: string }[] = [
  { value: "NEW", label: "New", empty: "Nothing new right now. The agent keeps looking in the background." },
  {
    value: "READY",
    label: "Ready to Apply",
    empty: "Fresher roles at your dream companies show up here with a tailored résumé and cover letter. Add dream companies in Settings > Job Search.",
  },
  { value: "HIGH_MATCH", label: "High Match", empty: "No high matches yet. Verifying more of your profile helps." },
  { value: "DEADLINE_SOON", label: "Closing Soon", empty: "No deadlines in the next week." },
  { value: "SAVED", label: "Saved", empty: "Tap the bookmark on any role to keep it here." },
  { value: "ALL", label: "All", empty: "No roles discovered yet. Add a job source in Settings." },
  { value: "DISMISSED", label: "Dismissed", empty: "Roles you dismiss end up here, in case you change your mind." },
  { value: "CLOSED", label: "Closed", empty: "Roles that close or disappear from their source show up here." },
];

export const SORTS: { value: JobSort; label: string }[] = [
  { value: "SCORE", label: "Best Match" },
  { value: "RECENT", label: "Newest" },
  { value: "DEADLINE", label: "Deadline" },
];

function isJobView(value: unknown): value is JobView {
  return JOB_VIEWS.some((view) => view.value === value);
}

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function JobsScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const { prefs, set } = usePrefs();
  const insets = useSafeAreaInsets();
  // The selected view lives in the route so other screens can deep-link into it.
  const params = useLocalSearchParams<{ view?: string }>();
  const view: JobView = isJobView(params.view) ? params.view : prefs.defaultJobView;
  const [search, setSearch] = useState("");
  const query = useDebounced(search.trim(), 350);
  const jobs = useJobs(view, query, prefs.jobSort);
  const keep = useJobFilter();
  const refresh = useRefresh(() => jobs.refetch());
  const refreshControl = useRefreshControl(refresh);

  const items = (jobs.data?.pages.flatMap((page) => page.items) ?? []).filter(keep);
  const total = jobs.data?.pages[0]?.total;
  const current = JOB_VIEWS.find((option) => option.value === view) ?? JOB_VIEWS[0];
  const hiddenByFilters = (jobs.data?.pages.flatMap((page) => page.items).length ?? 0) - items.length;

  const header = (
    <View style={{ gap: theme.space.md, paddingBottom: theme.space.sm }}>
      <View style={styles.titleRow}>
        <T v="largeTitle">Jobs</T>
        {total != null ? (
          <T v="subhead" color={colors.text2}>
            {total} {total === 1 ? "role" : "roles"}
          </T>
        ) : null}
      </View>
      <View style={[styles.search, { backgroundColor: colors.fill, borderRadius: theme.radius.small + 2 }]}>
        <Ionicons name="search" size={17} color={colors.text2} />
        <TextInput
          value={search}
          onChangeText={setSearch}
          placeholder="Search title, company or skill"
          placeholderTextColor={colors.text2}
          selectionColor={theme.accent}
          style={[theme.type.body, styles.searchInput, { color: colors.text, lineHeight: undefined }]}
          autoCorrect={false}
          returnKeyType="search"
          accessibilityLabel="Search jobs"
        />
        {search ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Clear search" hitSlop={10} onPress={() => setSearch("")}>
            <Ionicons name="close-circle" size={17} color={colors.text3} />
          </Pressable>
        ) : null}
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.pills} style={{ marginHorizontal: -theme.space.lg }}>
        {JOB_VIEWS.map((option) => {
          const active = option.value === view;
          return (
            <Pressable
              key={option.value}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              onPress={() => {
                theme.haptic("select");
                router.setParams({ view: option.value });
              }}
              style={[styles.pill, { backgroundColor: active ? colors.text : theme.colors.card, borderRadius: theme.radius.pill }]}
            >
              <T v="subhead" color={active ? "#FFFFFF" : colors.text} style={active ? theme.type.headline : undefined}>
                {option.label}
              </T>
            </Pressable>
          );
        })}
      </ScrollView>
      {view !== "DEADLINE_SOON" ? (
        <Segmented options={SORTS} value={prefs.jobSort} onChange={(jobSort) => set({ jobSort })} />
      ) : null}
      {hiddenByFilters > 0 ? (
        <Pressable accessibilityRole="button" onPress={() => router.push("/settings/jobs")}>
          <T v="footnote" color={colors.text2}>
            {hiddenByFilters} hidden by your filters · <T v="footnote" color={theme.accent}>Change</T>
          </T>
        </Pressable>
      ) : null}
    </View>
  );

  return (
    <View style={{ flex: 1, backgroundColor: colors.background }}>
      <FlatList
        data={items}
        keyExtractor={(job) => job.job_id}
        renderItem={({ item }) => <JobCardView job={item} />}
        ListHeaderComponent={header}
        contentContainerStyle={{
          paddingHorizontal: theme.space.lg,
          paddingTop: insets.top + theme.space.md,
          paddingBottom: TAB_BAR_SPACE + insets.bottom + theme.space.lg,
          gap: theme.space.md,
          flexGrow: 1,
        }}
        refreshControl={refreshControl}
        keyboardDismissMode="on-drag"
        keyboardShouldPersistTaps="handled"
        onEndReachedThreshold={0.5}
        onEndReached={() => {
          if (jobs.hasNextPage && !jobs.isFetchingNextPage) void jobs.fetchNextPage();
        }}
        ListEmptyComponent={
          jobs.isPending ? (
            <ActivityIndicator color={colors.text2} style={{ marginTop: theme.space.xxl }} />
          ) : jobs.isError ? (
            <Card>
              <EmptyState
                icon="cloud-offline-outline"
                title="Couldn't load jobs"
                message={jobs.error.message}
                action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void jobs.refetch()} />}
              />
            </Card>
          ) : (
            <EmptyState
              icon={query ? "search" : "briefcase-outline"}
              title={query ? `No results for “${query}”` : `No ${current.label.toLowerCase()} roles`}
              message={query ? "Try a different search or filter." : current.empty}
            />
          )
        }
        ListFooterComponent={jobs.isFetchingNextPage ? <ActivityIndicator color={colors.text2} style={{ marginVertical: theme.space.lg }} /> : null}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  titleRow: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between" },
  search: { flexDirection: "row", alignItems: "center", gap: 6, height: 38, paddingHorizontal: 9 },
  searchInput: { flex: 1, paddingVertical: 0 },
  pills: { gap: 8, paddingHorizontal: 16 },
  pill: { paddingHorizontal: 14, paddingVertical: 7 },
});
