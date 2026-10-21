export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export type ProcessBox = {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  score: number | null;
};

export type ProcessResponse = {
  boxes: ProcessBox[];
  overlay_png_base64: string;
  original_text: string;
  cleaned_text: string;
};

export const REGION_CONCEPTS = ["stamp", "signature", "photograph", "rectangle"] as const;

const ACCEPTED_TYPES = new Set(["image/jpeg", "image/jpg", "image/png"]);

export type ProcessRequest = {
  concepts?: readonly string[];
  fetchImpl?: typeof fetch;
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
  };
}

export function conceptsField(concepts: readonly string[] | undefined): string {
  const source = concepts ?? REGION_CONCEPTS;
  return REGION_CONCEPTS.filter((concept) => source.includes(concept)).join(",");
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
  const endpoint = `${apiBase.replace(/\/$/, "")}/api/process`;

  let response: Response;
  try {
    response = await fetchImpl(endpoint, { method: "POST", body });
  } catch {
    throw new Error("Could not reach the cleaner. Start the backend and try again.");
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
    throw new Error("The cleaner returned an unexpected response");
  }
  return parseProcessResponse(payload);
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
