"use client";

import { UserCheck, FileWarning, CalendarClock, XCircle } from "lucide-react";

type Eligibility = {
  who_can_apply: string[];
  required_documents: string[];
  conditions: string[];
  exclusions: string[];
};

type Deadline = { description: string; date: string | null };

function Section({ icon, title, items }: { icon: React.ReactNode; title: string; items: string[] }) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <div className="flex items-center gap-2 text-teal-dark">
        {icon}
        <h3 className="font-semibold">{title}</h3>
      </div>
      <ul className="mt-2 space-y-1 pl-7 text-base leading-relaxed text-ink/90">
        {items.map((item, i) => (
          <li key={i} className="list-disc">{item}</li>
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
  return (
    <div className="rounded-3xl bg-white p-6 shadow-sm space-y-5">
      <h2 className="font-display text-2xl font-bold text-teal-dark">Eligibility</h2>
      <Section icon={<UserCheck className="h-5 w-5" />} title="Who can apply" items={eligibility?.who_can_apply} />
      <Section icon={<FileWarning className="h-5 w-5" />} title="Documents you'll need" items={eligibility?.required_documents} />
      <Section icon={<UserCheck className="h-5 w-5" />} title="Conditions" items={eligibility?.conditions} />
      <Section icon={<XCircle className="h-5 w-5" />} title="Who is excluded" items={eligibility?.exclusions} />

      {deadlines?.length > 0 && (
        <div>
          <div className="flex items-center gap-2 text-amber-dark">
            <CalendarClock className="h-5 w-5" />
            <h3 className="font-semibold">Deadlines</h3>
          </div>
          <ul className="mt-2 space-y-1 pl-7 text-base text-ink/90">
            {deadlines.map((d, i) => (
              <li key={i}>
                {d.description}
                {d.date ? <span className="ml-2 font-semibold text-amber-dark">({d.date})</span> : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}