import { readErrorDetail, type DocumentField } from "./process-client.ts";

export const MAX_QUESTION_CHARS = 300;
export const MAX_TEXT_CHARS = 20_000;
// One Muse call with a 60 s timeout, plus some headroom.
const ASK_TIMEOUT_MS = 75_000;

export type AskAnswer = { answer: string; quote: string | null };

const SUGGESTED: Record<string, readonly string[]> = {
  invoice: ["What is the total due?", "When is it due?", "Who is it from?"],
  receipt: ["What was the total?", "Where was this bought?", "How was it paid?"],
  form: ["Whose form is this?", "What is the form for?", "When was it signed?"],
  id_document: ["Whose document is this?", "When does it expire?", "What is the ID number?"],
  letter: ["Who wrote this letter?", "What does it ask for?", "Is there a deadline?"],
  chat: ["What was agreed?", "Who is talking?", "Are any dates or times mentioned?"],
  note: ["What does the note ask for?", "Are any names or numbers mentioned?", "When is it for?"],
};
const GENERAL = ["What is this document about?", "Are any dates mentioned?", "Are any amounts mentioned?"];

export function suggestedQuestions(type: string | null | undefined): readonly string[] {
  return (type && SUGGESTED[type]) || GENERAL;
}

/** Check a question the way the API will. */
export function questionProblem(question: string): string | null {
  if (!question.trim()) {
    return "Type a question.";
  }
  if (question.length > MAX_QUESTION_CHARS) {
    return `Keep the question under ${MAX_QUESTION_CHARS} characters.`;
  }
  return null;
}

export async function askDocument(
  apiBase: string,
  request: { question: string; text: string; fields?: readonly DocumentField[] },
  options: { fetchImpl?: typeof fetch; signal?: AbortSignal; timeoutMs?: number } = {},
): Promise<AskAnswer> {
  const problem = questionProblem(request.question);
  if (problem) {
    throw new Error(problem);
  }
  const fetchImpl = options.fetchImpl ?? fetch;
  const timer = new AbortController();
  const timeoutId = setTimeout(() => timer.abort(), options.timeoutMs ?? ASK_TIMEOUT_MS);
  const signal = options.signal ? AbortSignal.any([options.signal, timer.signal]) : timer.signal;
  try {
    return await send(fetchImpl, apiBase, request, signal, timer.signal);
  } finally {
    clearTimeout(timeoutId);
  }
}

async function send(
  fetchImpl: typeof fetch,
  apiBase: string,
  request: { question: string; text: string; fields?: readonly DocumentField[] },
  signal: AbortSignal,
  timeout: AbortSignal,
): Promise<AskAnswer> {
  let response: Response;
  try {
    response = await fetchImpl(`${apiBase.replace(/\/$/, "")}/api/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        question: request.question,
        // The API caps the text; the start of a very long page still gets an answer.
        text: request.text.slice(0, MAX_TEXT_CHARS),
        fields: (request.fields ?? []).map(({ label, value }) => ({ label, value })),
      }),
      signal,
    });
  } catch {
    if (timeout.aborted) {
      throw new Error("The answer took too long. Try again.");
    }
    throw new Error("Could not reach the cleaner. Start the backend and try again.");
  }
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    throw new Error(readErrorDetail(response.status, payload));
  }
  const body = (payload ?? {}) as Record<string, unknown>;
  if (typeof body.answer !== "string" || !body.answer.trim()) {
    throw new Error("The cleaner returned an unexpected answer.");
  }
  return { answer: body.answer, quote: typeof body.quote === "string" ? body.quote : null };
}
