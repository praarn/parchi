"use client";

import { UserCheck, FileText, ListChecks, XCircle, CalendarClock } from "lucide-react";

type Eligibility = {
  who_can_apply: string[];
  required_documents: string[];
  conditions: string[];
  exclusions: string[];
};

type Deadline = { description: string; date: string | null };

function Section({
  icon,
  title,
  items,
  tone = "teal",
}: {
  icon: React.ReactNode;
  title: string;
  items: string[];
  tone?: "teal" | "danger";
}) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <div
        className={`flex items-center gap-2 text-sm font-semibold ${
          tone === "danger" ? "text-danger" : "text-teal-dark"
        }`}
      >
        {icon}
        <h3>{title}</h3>
      </div>
      <ul className="mt-2 space-y-1.5 pl-6 text-[15px] leading-relaxed text-ink-soft">
        {items.map((item, i) => (
          <li key={i} className="list-disc marker:text-line">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function EligibilityChecklist({
  eligibility,
  deadlines,
}: {
  eligibility: Eligibility;
  deadlines: Deadline[];
}) {
  const empty =
    !eligibility ||
    (["who_can_apply", "required_documents", "conditions", "exclusions"] as const).every(
      (k) => !eligibility[k]?.length,
    );

  return (
    <section className="card animate-fade-up space-y-5 p-6">
      <h2 className="font-display text-xl font-bold text-teal-dark">Eligibility &amp; dates</h2>

      {empty && (!deadlines || deadlines.length === 0) ? (
        <p className="text-[15px] text-ink-muted">
          This document doesn&apos;t set out specific eligibility rules or deadlines.
        </p>
      ) : (
        <>
          <Section
            icon={<UserCheck className="h-4 w-4" />}
            title="Who can apply"
            items={eligibility?.who_can_apply}
          />
          <Section
            icon={<FileText className="h-4 w-4" />}
            title="Documents you'll need"
            items={eligibility?.required_documents}
          />
          <Section
            icon={<ListChecks className="h-4 w-4" />}
            title="Conditions"
            items={eligibility?.conditions}
          />
          <Section
            icon={<XCircle className="h-4 w-4" />}
            title="Who is excluded"
            items={eligibility?.exclusions}
            tone="danger"
          />

          {deadlines?.length > 0 && (
            <div>
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-dark">
                <CalendarClock className="h-4 w-4" />
                <h3>Key dates</h3>
              </div>
              <ul className="mt-2 space-y-1.5 pl-6 text-[15px] text-ink-soft">
                {deadlines.map((d, i) => (
                  <li key={i} className="list-disc marker:text-line">
                    {d.description}
                    {d.date && (
                      <span className="ml-2 rounded bg-amber-wash px-1.5 py-0.5 text-xs font-semibold text-amber-dark">
                        {d.date}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}
