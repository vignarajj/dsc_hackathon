/** Sample pages made for this app. None holds real personal data. */
export const SAMPLES = [
  { id: "invoice", label: "Invoice with a PAID stamp" },
  { id: "signed-form", label: "Signed form with a photo" },
  { id: "handwritten-note", label: "Handwritten note" },
  { id: "chat", label: "Chat screenshot" },
] as const;

export type SampleId = (typeof SAMPLES)[number]["id"];

export function sampleUrl(id: SampleId): string {
  return `/samples/${id}.jpg`;
}

export function sampleThumbUrl(id: SampleId): string {
  return `/samples/thumbs/${id}.jpg`;
}

/** Fetch a sample as a File, so it goes through the same path as an upload. */
export async function loadSample(id: SampleId, fetchImpl: typeof fetch = fetch): Promise<File> {
  const response = await fetchImpl(sampleUrl(id));
  if (!response.ok) {
    throw new Error("Could not load the sample. Try again, or choose your own file.");
  }
  const blob = await response.blob();
  return new File([blob], `${id}.jpg`, { type: "image/jpeg" });
}
