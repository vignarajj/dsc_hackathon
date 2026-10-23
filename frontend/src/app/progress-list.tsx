import type { StageState } from "@/lib/process-client";

const STAGE_LABELS: Record<string, string> = {
  prepare: "Preparing the image",
  segment: "Finding regions with SAM",
  describe: "Describing each region",
  transcribe: "Reading the text with Muse",
  proofread: "Proofreading",
  extract: "Pulling out key fields",
  privacy: "Finding personal details",
  render: "Building the overlay and share-safe copy",
};

const STATUS_TEXT = { waiting: "Waiting", running: "In progress", done: "Done" } as const;

export function ProgressList({ stages }: { stages: readonly StageState[] }) {
  return (
    <ol aria-label="Progress" className="flex flex-col gap-1.5 text-sm">
      {stages.map(({ stage, status, detail }) => (
        <li
          key={stage}
          className={`flex items-center gap-2 ${status === "waiting" ? "text-muted" : ""}`}
        >
          <span
            aria-hidden="true"
            className={`inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px] ${
              status === "done"
                ? "border-stamp bg-stamp text-stamp-ink"
                : status === "running"
                  ? "animate-pulse border-stamp"
                  : "border-line"
            }`}
          >
            {status === "done" ? "✓" : ""}
          </span>
          <span>{STAGE_LABELS[stage] ?? stage}</span>
          <span className="sr-only">: {STATUS_TEXT[status]}</span>
          {detail && status === "done" ? <span className="text-xs text-muted">{detail}</span> : null}
        </li>
      ))}
    </ol>
  );
}
