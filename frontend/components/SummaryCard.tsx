"use client";

import { CheckCircle2, Sparkles } from "lucide-react";

type Insight = {
  summary: string;
  key_points: string[];
  explain_like_10: string;
};

export function SummaryCard({ insight }: { insight: Insight }) {
  return (
    <section className="card animate-fade-up p-6">
      <h2 className="font-display text-xl font-bold text-teal-dark">Summary</h2>
      <p className="mt-3 text-[17px] leading-relaxed text-ink">{insight.summary}</p>

      {insight.key_points?.length > 0 && (
        <ul className="mt-5 space-y-2.5">
          {insight.key_points.map((point, i) => (
            <li key={i} className="flex gap-2.5 text-[15px] leading-relaxed text-ink-soft">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-teal" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
      )}

      {insight.explain_like_10 && (
        <details className="group mt-5 rounded-xl bg-amber-wash/70 p-4">
          <summary className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-amber-dark">
            <Sparkles className="h-4 w-4" />
            Explain it like I&apos;m 10
          </summary>
          <p className="mt-2 text-[15px] leading-relaxed text-ink-soft">
            {insight.explain_like_10}
          </p>
        </details>
      )}
    </section>
  );
}
