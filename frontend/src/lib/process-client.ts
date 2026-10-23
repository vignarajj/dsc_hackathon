export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

// The API can spend 60 s on segmentation and transcription, 60 s on the
// proofread, and 60 s finding sensitive text in the picture when that is on.
export const REQUEST_TIMEOUT_MS = 180_000;

export type ProcessBox = {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  score: number | null;
};

export type ProcessModels = {
  segmentation: string;
  transcription: string;
  proofread: string;
  signatures: string | null;
};

export type SensitiveItem = {
  category: string;
  text: string;
  source: string;
};

export type DocumentField = {
  label: string;
  value: string;
  found_in_text: boolean;
};

export type DocumentData = {
  type: string;
  title: string;
  summary: string;
  fields: DocumentField[];
};

export type ProcessResponse = {
  boxes: ProcessBox[];
  overlay_png_base64: string;
  original_text: string;
  cleaned_text: string;
  models: ProcessModels | null;
  redacted_png_base64: string | null;
  sensitive: SensitiveItem[];
  shareable_text: string | null;
  image_text_hidden: boolean;
  palette: Record<string, string>;
  document: DocumentData | null;
  warnings: string[];
};

export type RedactStyle = "black" | "blur";

export type RegionCount = {
  label: string;
  count: number;
  bestScore: number | null;
};

/** Thrown when the user cancels a request, so the page can reset quietly. */
export class CancelledError extends Error {
  constructor() {
    super("Cancelled");
    this.name = "CancelledError";
  }
}

export const REGION_CONCEPTS = ["stamp", "signature", "photograph", "rectangle"] as const;

/** Regions the share-safe copy can hide. Rectangles are layout, not private. */
export const HIDEABLE_REGIONS = ["signature", "photograph", "stamp"] as const;

export const MAX_CUSTOM = 3;

/** Custom prompts that SAM found in the F0 spike. */
export const CUSTOM_SUGGESTIONS = [
  "logo",
  "qr code",
  "barcode",
  "face",
  "table",
  "checkbox",
  "seal",
] as const;

/** The API colors custom regions in this order. */
export const CUSTOM_PALETTE = ["#7c3aed", "#0d9488", "#db2777"] as const;

// These mirror the API rules in backend/src/dsc_backend/form.py.
const CUSTOM_ALIASES: Record<string, string> = {
  photo: "photograph",
  stamps: "stamp",
  signatures: "signature",
};
const CUSTOM_PATTERN = /^[a-z][a-z -]{0,29}$/;
const BLOCKED_CUSTOM = new Set([
  "text",
  "document",
  "printed text",
  "receipt",
  "handwritten note",
  "handwriting",
  "handwritten text",
]);

export type CustomChoice =
  | { kind: "preset"; name: (typeof REGION_CONCEPTS)[number] }
  | { kind: "custom"; name: string }
  | { kind: "error"; message: string };

/** Check a typed region name the way the API will. */
export function customChoice(raw: string, existing: readonly string[]): CustomChoice {
  const typed = raw.toLowerCase().split(/\s+/).filter(Boolean).join(" ");
  const name = CUSTOM_ALIASES[typed] ?? typed;
  if (!name) {
    return { kind: "error", message: "Type what to find, like logo." };
  }
  const preset = REGION_CONCEPTS.find((concept) => concept === name);
  if (preset) {
    return { kind: "preset", name: preset };
  }
  if (!CUSTOM_PATTERN.test(name) || name.split(" ").length > 3) {
    return { kind: "error", message: "Describe what to find in 1 to 3 plain words, like logo." };
  }
  if (BLOCKED_CUSTOM.has(name)) {
    return { kind: "error", message: "SAM marks objects, not text. Try a stamp, logo, or QR code." };
  }
  if (existing.includes(name)) {
    return { kind: "error", message: `${name} is already on the list.` };
  }
  if (existing.length >= MAX_CUSTOM) {
    return { kind: "error", message: `Add up to ${MAX_CUSTOM} things to find.` };
  }
  return { kind: "custom", name };
}

const ACCEPTED_TYPES = new Set(["image/jpeg", "image/jpg", "image/png"]);

export type ProcessRequest = {
  concepts?: readonly string[];
  custom?: readonly string[];
  redact?: readonly string[];
  redactStyle?: RedactStyle;
  redactText?: boolean;
  extract?: boolean;
  fetchImpl?: typeof fetch;
  signal?: AbortSignal;
  timeoutMs?: number;
};

export function validateImageFile(file: { type: string; size: number }): string | null {
  const mediaType = file.type.split(";", 1)[0]?.trim().toLowerCase() ?? "";
  if (!ACCEPTED_TYPES.has(mediaType)) {
    return "Only JPEG and PNG images are accepted";
  }
  if (file.size === 0) {
    return "Image file is empty";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "Image exceeds the 10 MB limit";
  }
  return null;
}

export function readErrorDetail(status: number, body: unknown): string {
  if (body && typeof body === "object" && "detail" in body && typeof body.detail === "string") {
    const detail = body.detail.trim();
    if (detail) {
      return detail;
    }
  }
  if (status === 413) {
    return "Image exceeds the 10 MB limit";
  }
  if (status === 429) {
    return "Too many requests. Wait a minute and try again.";
  }
  if (status === 502) {
    return "The model request failed";
  }
  return `Request failed (${status})`;
}

export function parseProcessResponse(body: unknown): ProcessResponse {
  if (!body || typeof body !== "object") {
    throw new Error("The cleaner returned an unexpected response");
  }
  const record = body as Record<string, unknown>;
  if (typeof record.overlay_png_base64 !== "string" || record.overlay_png_base64.length === 0) {
    throw new Error("The cleaner returned an unexpected response");
  }
  if (typeof record.original_text !== "string" || typeof record.cleaned_text !== "string") {
    throw new Error("The cleaner returned an unexpected response");
  }
  if (!Array.isArray(record.boxes)) {
    throw new Error("The cleaner returned an unexpected response");
  }
  return {
    boxes: record.boxes.flatMap(parseBox),
    overlay_png_base64: record.overlay_png_base64,
    original_text: record.original_text,
    cleaned_text: record.cleaned_text,
    models: parseModels(record.models),
    redacted_png_base64:
      typeof record.redacted_png_base64 === "string" && record.redacted_png_base64.length > 0
        ? record.redacted_png_base64
        : null,
    sensitive: Array.isArray(record.sensitive) ? record.sensitive.flatMap(parseSensitive) : [],
    shareable_text: typeof record.shareable_text === "string" ? record.shareable_text : null,
    image_text_hidden: record.image_text_hidden === true,
    palette: parsePalette(record.palette),
    document: parseDocument(record.document),
    warnings: Array.isArray(record.warnings)
      ? record.warnings.filter((item): item is string => typeof item === "string")
      : [],
  };
}

/** Count boxes per requested region: presets in canonical order, then custom ones. */
export function regionCounts(
  boxes: readonly ProcessBox[],
  concepts: readonly string[],
): RegionCount[] {
  return orderedLabels(concepts, []).map((label) => {
    const matching = boxes.filter((box) => box.label === label);
    const scores = matching.flatMap((box) => (box.score === null ? [] : [box.score]));
    return {
      label,
      count: matching.length,
      bestScore: scores.length > 0 ? Math.max(...scores) : null,
    };
  });
}

export function conceptsField(concepts: readonly string[] | undefined): string {
  const source = concepts ?? REGION_CONCEPTS;
  return REGION_CONCEPTS.filter((concept) => source.includes(concept)).join(",");
}

/** The regions to hide, limited to the marked ones, since the API rejects the rest. */
export function redactField(
  redact: readonly string[] | undefined,
  concepts: readonly string[] | undefined,
  custom: readonly string[] = [],
): string {
  const marked = conceptsField(concepts).split(",").filter(Boolean);
  return orderedLabels(marked, custom)
    .filter((label) => (redact ?? []).includes(label))
    .join(",");
}

/** Presets in canonical order, then every other label in the order given. */
function orderedLabels(labels: readonly string[], custom: readonly string[]): string[] {
  const all = [...labels, ...custom];
  const presets: string[] = REGION_CONCEPTS.filter((concept) => all.includes(concept));
  const others = all.filter(
    (label, index) => !presets.includes(label) && all.indexOf(label) === index,
  );
  return [...presets, ...others];
}

export async function processImage(
  file: File,
  apiBase: string,
  request: ProcessRequest = {},
): Promise<ProcessResponse> {
  const problem = validateImageFile(file);
  if (problem) {
    throw new Error(problem);
  }
  const fetchImpl = request.fetchImpl ?? fetch;

  const body = new FormData();
  body.append("image", file);
  body.append("concepts", conceptsField(request.concepts));
  body.append("custom", (request.custom ?? []).join(","));
  body.append("redact", redactField(request.redact, request.concepts, request.custom));
  body.append("redact_style", request.redactStyle ?? "black");
  body.append("redact_text", request.redactText ? "true" : "false");
  body.append("extract", request.extract ? "true" : "false");
  const endpoint = `${apiBase.replace(/\/$/, "")}/api/process`;
  const timer = new AbortController();
  const timeoutId = setTimeout(() => timer.abort(), request.timeoutMs ?? REQUEST_TIMEOUT_MS);
  const timeout = timer.signal;
  const signal = request.signal ? AbortSignal.any([request.signal, timeout]) : timeout;

  try {
    return await send(fetchImpl, endpoint, body, signal, request.signal, timeout);
  } finally {
    clearTimeout(timeoutId);
  }
}

async function send(
  fetchImpl: typeof fetch,
  endpoint: string,
  body: FormData,
  signal: AbortSignal,
  cancel: AbortSignal | undefined,
  timeout: AbortSignal,
): Promise<ProcessResponse> {
  let response: Response;
  try {
    response = await fetchImpl(endpoint, { method: "POST", body, signal });
  } catch {
    throw abortError(cancel, timeout) ??
      new Error("Could not reach the cleaner. Start the backend and try again.");
  }

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new Error(readErrorDetail(response.status, payload));
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw abortError(cancel, timeout) ??
      new Error("The cleaner returned an unexpected response");
  }
  return parseProcessResponse(payload);
}

function abortError(cancel: AbortSignal | undefined, timeout: AbortSignal): Error | null {
  if (cancel?.aborted) {
    return new CancelledError();
  }
  if (timeout.aborted) {
    return new Error("The cleaner took too long to answer. Try again.");
  }
  return null;
}

function parseModels(value: unknown): ProcessModels | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const models = value as Record<string, unknown>;
  if (
    typeof models.segmentation !== "string" ||
    typeof models.transcription !== "string" ||
    typeof models.proofread !== "string"
  ) {
    return null;
  }
  return {
    segmentation: models.segmentation,
    transcription: models.transcription,
    proofread: models.proofread,
    signatures: typeof models.signatures === "string" ? models.signatures : null,
  };
}

function parseBox(value: unknown): ProcessBox[] {
  if (!value || typeof value !== "object") {
    return [];
  }
  const box = value as Record<string, unknown>;
  if (
    typeof box.x !== "number" ||
    typeof box.y !== "number" ||
    typeof box.w !== "number" ||
    typeof box.h !== "number" ||
    typeof box.label !== "string"
  ) {
    return [];
  }
  const score = typeof box.score === "number" ? box.score : null;
  return [{ x: box.x, y: box.y, w: box.w, h: box.h, label: box.label, score }];
}

function parseSensitive(value: unknown): SensitiveItem[] {
  if (!value || typeof value !== "object") {
    return [];
  }
  const item = value as Record<string, unknown>;
  if (
    typeof item.category !== "string" ||
    typeof item.text !== "string" ||
    typeof item.source !== "string"
  ) {
    return [];
  }
  return [{ category: item.category, text: item.text, source: item.source }];
}

function parsePalette(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object") {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value as Record<string, unknown>).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === "string" && /^#[0-9a-f]{6}$/i.test(entry[1]),
    ),
  );
}

function parseDocument(value: unknown): DocumentData | null {
  if (!value || typeof value !== "object") {
    return null;
  }
  const data = value as Record<string, unknown>;
  if (
    typeof data.type !== "string" ||
    typeof data.title !== "string" ||
    typeof data.summary !== "string" ||
    !Array.isArray(data.fields)
  ) {
    return null;
  }
  return {
    type: data.type,
    title: data.title,
    summary: data.summary,
    fields: data.fields.flatMap((item: unknown): DocumentField[] => {
      if (!item || typeof item !== "object") {
        return [];
      }
      const field = item as Record<string, unknown>;
      if (typeof field.label !== "string" || typeof field.value !== "string") {
        return [];
      }
      return [{ label: field.label, value: field.value, found_in_text: field.found_in_text === true }];
    }),
  };
}
