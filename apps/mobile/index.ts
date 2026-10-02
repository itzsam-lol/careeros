// Background tasks must be defined as the bundle loads. Android runs them without opening any
// screen, so a task defined only by a route or layout module would never be found.
import "@/lib/alerts";
import "expo-router/entry";
