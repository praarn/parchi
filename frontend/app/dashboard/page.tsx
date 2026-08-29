"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FileText, ImageIcon } from "lucide-react";
import { Header } from "@/components/Header";
import { Toast } from "@/components/Toast";
import { StatusBadge } from "@/components/StatusBadge";
import { UploadDropzone } from "@/components/UploadDropzone";
import { api, isAuthed } from "@/lib/api-client";

type Doc = {
  id: string;
  original_filename: string | null;
  mime_type: string | null;
  status: string;
  page_count: number | null;
  created_at: string;
};

type Stats = {
  total: number;
  by_status: Record<string, number>;
  avg_page_count: number | null;
  uploads_last_14_days: { day: string; count: number }[];
};

export default function DashboardPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [list, s] = await Promise.all([api.listDocuments({ limit: 50 }), api.getStats()]);
      setDocs(list.documents);
      setStats(s);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isAuthed()) {
      router.replace("/login");
      return;
    }
    load();
  }, [router, load]);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      const { document } = await api.uploadDocument(file);
      await api.processDocument(document.id);
      router.push(`/document/${document.id}`);
    } catch (err: any) {
      setError(err.message);
      setUploading(false);
    }
  }

  const peak = Math.max(1, ...(stats?.uploads_last_14_days.map((d) => d.count) ?? [1]));

  return (
    <main>
      <Header authed right={<span className="text-sm text-ink-muted">Your documents</span>} />
      <Toast message={error} onClose={() => setError(null)} />

      <div className="mx-auto max-w-5xl space-y-8 px-6 py-10">
        <section>
          <h1 className="font-display text-2xl font-bold text-ink">Add a document</h1>
          <p className="mt-1 text-ink-muted">
            Upload a government notice, form or letter — a PDF or a photo.
          </p>
          <div className="mt-4">
            <UploadDropzone onFileSelected={handleFile} onReject={setError} busy={uploading} />
          </div>
        </section>

        {stats && stats.total > 0 && (
          <section className="grid gap-4 sm:grid-cols-3">
            <div className="card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Documents
              </p>
              <p className="mt-1 font-display text-3xl font-bold text-teal-dark">{stats.total}</p>
            </div>
            <div className="card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Ready</p>
              <p className="mt-1 font-display text-3xl font-bold text-teal-dark">
                {stats.by_status.ready ?? 0}
              </p>
            </div>
            <div className="card p-5">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Avg. pages
              </p>
              <p className="mt-1 font-display text-3xl font-bold text-teal-dark">
                {stats.avg_page_count ?? "—"}
              </p>
            </div>
            <div className="card p-5 sm:col-span-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">
                Uploads · last 14 days
              </p>
              <div className="mt-3 flex h-16 items-end gap-1.5">
                {stats.uploads_last_14_days.map((d) => (
                  <div key={d.day} className="flex-1" title={`${d.day}: ${d.count}`}>
                    <div
                      className="w-full rounded-t bg-teal/70"
                      style={{ height: `${(d.count / peak) * 100}%`, minHeight: d.count ? 4 : 1 }}
                    />
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        <section>
          <h2 className="mb-3 font-display text-xl font-bold text-ink">Recent</h2>
          {loading ? (
            <p className="text-ink-muted">Loading…</p>
          ) : docs.length === 0 ? (
            <p className="rounded-card border border-dashed border-line p-8 text-center text-ink-muted">
              Nothing here yet. Upload your first document above.
            </p>
          ) : (
            <ul className="divide-y divide-line overflow-hidden rounded-card border border-line bg-paper-raised">
              {docs.map((d) => (
                <li key={d.id}>
                  <Link
                    href={`/document/${d.id}`}
                    className="flex items-center gap-4 px-5 py-4 transition hover:bg-paper-sunk"
                  >
                    <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-wash text-teal">
                      {d.mime_type?.startsWith("image/") ? (
                        <ImageIcon className="h-4 w-4" />
                      ) : (
                        <FileText className="h-4 w-4" />
                      )}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium text-ink">
                        {d.original_filename || "Untitled document"}
                      </span>
                      <span className="text-xs text-ink-muted">
                        {new Date(d.created_at).toLocaleDateString()}
                        {d.page_count ? ` · ${d.page_count} page${d.page_count > 1 ? "s" : ""}` : ""}
                      </span>
                    </span>
                    <StatusBadge status={d.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
