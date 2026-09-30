import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

/**
 * Small key/value store: the Android/iOS keystore on devices, localStorage when the app
 * runs in a browser during development (expo-secure-store has no web implementation).
 */
const web = Platform.OS === "web";

export const storage = {
  async get(key: string): Promise<string | null> {
    if (web) return globalThis.localStorage?.getItem(key) ?? null;
    return SecureStore.getItemAsync(key);
  },
  async set(key: string, value: string): Promise<void> {
    if (web) {
      globalThis.localStorage?.setItem(key, value);
      return;
    }
    await SecureStore.setItemAsync(key, value);
  },
  async remove(key: string): Promise<void> {
    if (web) {
      globalThis.localStorage?.removeItem(key);
      return;
    }
    await SecureStore.deleteItemAsync(key);
  },
};
