import Ionicons from "@expo/vector-icons/Ionicons";
import { useEffect, useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, TextInput, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, EmptyState, Group, Loading, Row, Segmented, T } from "@/components/ui";
import { type CatalogBoard, useAddFromCatalog, useCatalog } from "@/lib/careers";
import { titleCase } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Region = "all" | "IN" | "AU";

const FLAGS: Record<string, string> = { IN: "\u{1F1EE}\u{1F1F3}", AU: "\u{1F1E6}\u{1F1FA}" };

function useDebounced<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

function BoardRow({ board, onAdd, adding }: { board: CatalogBoard; onAdd: () => void; adding: boolean }) {
  const theme = useTheme();
  return (
    <Row
      title={board.name}
      subtitle={`${board.regions.map((r) => `${FLAGS[r] ?? ""} ${r === "IN" ? "India" : "Australia"}`).join("  ")}  ·  ${titleCase(board.type)}`}
      right={
        board.added ? (
          <Ionicons name="checkmark-circle" size={24} color="#34C759" accessibilityLabel="Added" />
        ) : adding ? (
          <ActivityIndicator color={theme.colors.text2} />
        ) : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Add ${board.name}`}
            hitSlop={8}
            onPress={onAdd}
            style={({ pressed }) => [styles.add, { backgroundColor: theme.colors.accentSoft, borderRadius: theme.radius.pill, opacity: pressed ? 0.6 : 1 }]}
          >
            <T v="subhead" color={theme.accent}>
              Add
            </T>
          </Pressable>
        )
      }
    />
  );
}

export default function CatalogScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const [region, setRegion] = useState<Region>("all");
  const [search, setSearch] = useState("");
  const q = useDebounced(search.trim(), 300);
  const catalog = useCatalog(region === "all" ? undefined : region, q);
  const add = useAddFromCatalog();
  const refresh = useRefresh(() => catalog.refetch());
  const [pendingId, setPendingId] = useState<string | null>(null);

  const boards = catalog.data ?? [];
  const remaining = boards.filter((b) => !b.added);

  const addAll = () =>
    Alert.alert(
      `Add ${remaining.length} companies?`,
      "Each board is checked daily. First runs are spread out over the next hour, and new matches appear in Jobs as they're analysed.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Add All",
          onPress: () =>
            add.mutate(
              { ids: remaining.map((b) => b.id) },
              { onSuccess: (result) => Alert.alert("Added", `${result.added} companies added.`) },
            ),
        },
      ],
    );

  return (
    <Screen
      title="Browse Companies"
      subtitle="Public job boards verified to list roles in India or Australia. Australian roles only show when the posting offers visa sponsorship."
      back="Sources"
      backFallback="/settings"
      tabBar={false}
      refresh={refresh}
    >
      <View style={{ gap: theme.space.md }}>
        <View style={[styles.search, { backgroundColor: colors.fill, borderRadius: theme.radius.small + 2 }]}>
          <Ionicons name="search" size={17} color={colors.text2} />
          <TextInput
            value={search}
            onChangeText={setSearch}
            placeholder="Search companies"
            placeholderTextColor={colors.text2}
            autoCorrect={false}
            selectionColor={theme.accent}
            accessibilityLabel="Search companies"
            style={[theme.type.body, { flex: 1, color: colors.text, paddingVertical: 0, lineHeight: undefined }]}
          />
        </View>
        <Segmented
          options={[
            { value: "all", label: "All" },
            { value: "IN", label: "India" },
            { value: "AU", label: "Australia" },
          ]}
          value={region}
          onChange={setRegion}
        />
      </View>

      {catalog.isPending ? (
        <Loading />
      ) : catalog.isError ? (
        <Card>
          <EmptyState icon="cloud-offline-outline" title="Couldn't load the catalogue" message={catalog.error.message} />
        </Card>
      ) : boards.length === 0 ? (
        <EmptyState icon="business-outline" title="No companies found" message="Try a different search." />
      ) : (
        <>
          {remaining.length > 1 ? (
            <Button label={`Add All ${remaining.length} Shown`} icon="add-circle-outline" variant="tinted" onPress={addAll} loading={add.isPending && pendingId === null} />
          ) : null}
          <Group footer={`${boards.length} companies · ${boards.length - remaining.length} added`}>
            {boards.map((board) => (
              <BoardRow
                key={board.id}
                board={board}
                adding={add.isPending && pendingId === board.id}
                onAdd={() => {
                  setPendingId(board.id);
                  add.mutate({ ids: [board.id] }, { onSettled: () => setPendingId(null) });
                }}
              />
            ))}
          </Group>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  search: { flexDirection: "row", alignItems: "center", gap: 6, height: 38, paddingHorizontal: 9 },
  add: { paddingHorizontal: 14, paddingVertical: 6 },
});
