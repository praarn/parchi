"use client";

import { Check, Loader2 } from "lucide-react";

// Order matches the worker's pipeline. "vision" only fires for image uploads;
// it's shown once we've seen it so PDF runs don't display a stage they skip.
const STAGES: { key: string; label: string }[] = [
  { key: "extracting", label: "Reading the document" },
  { key: "vision", label: "Transcribing the image" },
  { key: "simplifying", label: "Writing a plain-language summary" },
  { key: "embedding", label: "Indexing it for questions" },
  { key: "tables", label: "Pulling out tables" },
  { key: "finalizing", label: "Finishing up" },
];

export function ProgressStages({ stage }: { stage: string | null }) {
  const seenVision = stage === "vision";
  const visible = STAGES.filter((s) => s.key !== "vision" || seenVision);
  const order = visible.map((s) => s.key);
  const currentIndex = stage ? order.indexOf(stage) : -1;

  return (
    <ol className="mx-auto max-w-sm space-y-3 text-left">
      {visible.map((s, i) => {
        const done = currentIndex > i;
        const active = currentIndex === i;
        return (
          <li key={s.key} className="flex items-center gap-3">
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border ${
                done
                  ? "border-teal bg-teal text-white"
                  : active
                    ? "border-teal text-teal"
                    : "border-line text-ink-muted"
              }`}
            >
              {done ? (
                <Check className="h-4 w-4" />
              ) : active ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
              )}
            </span>
            <span
              className={`text-sm ${
                active ? "font-semibold text-ink" : done ? "text-ink-soft" : "text-ink-muted"
              }`}
            >
              {s.label}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
