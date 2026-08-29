"use client";

import { Table2 } from "lucide-react";

type ParsedTable = {
  page_number: number | null;
  data: { columns: string[]; rows: string[][] } | null;
};

export function TablesCard({ tables }: { tables: ParsedTable[] }) {
  const usable = tables.filter((t) => t.data?.columns?.length);
  if (usable.length === 0) return null;

  return (
    <section className="card animate-fade-up p-6">
      <h2 className="flex items-center gap-2 font-display text-xl font-bold text-teal-dark">
        <Table2 className="h-5 w-5" />
        Tables in this document
      </h2>
      <div className="mt-4 space-y-6">
        {usable.map((t, ti) => (
          <div key={ti}>
            {t.page_number != null && (
              <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Page {t.page_number}
              </p>
            )}
            <div className="overflow-x-auto rounded-xl border border-line">
              <table className="w-full border-collapse text-left text-sm">
                <thead className="bg-paper-sunk text-ink-soft">
                  <tr>
                    {t.data!.columns.map((c, i) => (
                      <th key={i} className="px-3 py-2 font-semibold">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {t.data!.rows.map((row, ri) => (
                    <tr key={ri} className="border-t border-line">
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-3 py-2 text-ink-soft">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
