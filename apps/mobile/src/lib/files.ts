import * as DocumentPicker from "expo-document-picker";
import { File, Paths } from "expo-file-system";
import * as IntentLauncher from "expo-intent-launcher";
import * as Sharing from "expo-sharing";
import * as WebBrowser from "expo-web-browser";
import { Platform } from "react-native";

/** Download a (signed) PDF link into the cache and return the local file. */
async function download(url: string, filename: string): Promise<File> {
  const target = new File(Paths.cache, filename);
  if (target.exists) target.delete();
  return File.downloadFileAsync(url, target);
}

function safeName(title: string): string {
  return `${title.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 80) || "document"}.pdf`;
}

/** Open a PDF in the phone's PDF viewer (falls back to the share sheet, then the browser). */
export async function openPdf(url: string, title: string): Promise<void> {
  if (Platform.OS === "web") {
    await WebBrowser.openBrowserAsync(url);
    return;
  }
  const file = await download(url, safeName(title));
  if (Platform.OS === "android") {
    try {
      await IntentLauncher.startActivityAsync("android.intent.action.VIEW", {
        data: file.contentUri,
        flags: 1, // FLAG_GRANT_READ_URI_PERMISSION
        type: "application/pdf",
      });
      return;
    } catch {
      // No PDF viewer installed: offer the share sheet instead.
    }
  }
  await Sharing.shareAsync(file.uri, { mimeType: "application/pdf", dialogTitle: title, UTI: "com.adobe.pdf" });
}

/** Share a PDF (WhatsApp, Gmail, Drive, ...), e.g. to attach it to an application. */
export async function sharePdf(url: string, title: string): Promise<void> {
  if (Platform.OS === "web") {
    await WebBrowser.openBrowserAsync(url);
    return;
  }
  const file = await download(url, safeName(title));
  await Sharing.shareAsync(file.uri, { mimeType: "application/pdf", dialogTitle: title, UTI: "com.adobe.pdf" });
}

/** Let the user pick a .tex file and return its text (null if cancelled). */
export async function pickTexFile(): Promise<{ name: string; text: string } | null> {
  const result = await DocumentPicker.getDocumentAsync({ type: "*/*", copyToCacheDirectory: true, multiple: false });
  if (result.canceled || !result.assets?.length) return null;
  const asset = result.assets[0];
  if (!/\.(tex|txt)$/i.test(asset.name)) throw new Error("Choose a LaTeX (.tex) file");
  const text = await new File(asset.uri).text();
  return { name: asset.name.replace(/\.txt$/i, ""), text };
}
