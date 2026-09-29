export { ApiError, createApiClient, toApiError, unwrap } from "./client";
export type { ApiClient, ApiClientOptions } from "./client";
export type { components, paths } from "./schema";

import type { components } from "./schema";

/** Shorthand for API schema types: `Schema<"MeResponse">`. */
export type Schema<K extends keyof components["schemas"]> = components["schemas"][K];
