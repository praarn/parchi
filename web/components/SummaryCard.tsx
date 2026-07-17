"use client";

import { CheckCircle2 } from "lucide-react";

type Insight = {
  summary: string;
  key_points: string[];
  explain_like_10: string;
};

export function SummaryCard({ insight }: { insight: Insight }) {
  return (
    <div className="rounded-3xl bg-white p-6 shadow-sm">
      <h2 className="font-display text-2xl font-bold text-teal-dark">Summary</h2>
      <p className="mt-3 text-lg leading-relaxed text-ink">{insight.summary}</p>

      {insight.key_points?.length > 0 && (
        <ul className="mt-5 space-y-3">
          {insight.key_points.map((point, i) => (
            <li key={i} className="flex gap-3 text-base leading-relaxed">
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-teal" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}

      {insight.explain_like_10 && (
        <details className="mt-5 rounded-2xl bg-amber/10 p-4">
          <summary className="cursor-pointer text-base font-semibold text-amber-dark">
            Explain it like I&apos;m 10
          </summary>
          <p className="mt-2 text-base leading-relaxed text-ink">{insight.explain_like_10}</p>
        </details>
      )}
    </div>
  );
}