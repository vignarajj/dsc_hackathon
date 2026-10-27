export type ServerFeatures = {
  extract: boolean;
  describe: boolean;
  privacy: boolean;
  imageText: boolean;
};

/** What a server that does not say is assumed to run: the API defaults. */
export const DEFAULT_FEATURES: ServerFeatures = {
  extract: true,
  describe: true,
  privacy: true,
  imageText: false,
};

/** Ask the API which optional features it runs. Any failure keeps the defaults. */
export async function fetchFeatures(
  apiBase: string,
  fetchImpl: typeof fetch = fetch,
  signal?: AbortSignal,
): Promise<ServerFeatures> {
  try {
    const response = await fetchImpl(`${apiBase.replace(/\/$/, "")}/api/config`, { signal });
    if (!response.ok) {
      return DEFAULT_FEATURES;
    }
    const body = (await response.json()) as { features?: Record<string, unknown> };
    const features = body.features ?? {};
    const flag = (value: unknown, fallback: boolean) =>
      typeof value === "boolean" ? value : fallback;
    return {
      extract: flag(features.extract, DEFAULT_FEATURES.extract),
      describe: flag(features.describe, DEFAULT_FEATURES.describe),
      privacy: flag(features.privacy, DEFAULT_FEATURES.privacy),
      imageText: flag(features.image_text, DEFAULT_FEATURES.imageText),
    };
  } catch {
    return DEFAULT_FEATURES;
  }
}
