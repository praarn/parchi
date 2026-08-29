"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Share2 } from "lucide-react";
import { Header } from "@/components/Header";
import { Toast } from "@/components/Toast";
import { SummaryCard } from "@/components/SummaryCard";
import { EligibilityChecklist } from "@/components/EligibilityChecklist";
import { TablesCard } from "@/components/TablesCard";
import { ChatWindow } from "@/components/ChatWindow";
import { LanguageSelector } from "@/components/LanguageSelector";
import { ProgressStages } from "@/components/ProgressStages";
import { api } from "@/lib/api-client";
import { useDocumentProgress } from "@/lib/useDocumentProgress";

function parseMaybeJson(v: any) {
  return typeof v === "string" ? JSON.parse(v) : v;
}

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const [language, setLanguage] = useState("en");
  const [insight, setInsight] = useState<any>(null);
  const [tables, setTables] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { status, stage, settled } = useDocumentProgress(id, {
    status: "processing",
    stage: null,
  });

  const loadInsight = useCallback(
    async (lang: string) => {
      try {
        const res = await api.getDocument(id, lang);
        if (res.insight) setInsight(res.insight);
      } catch (err: any) {
        setError(err.message);
      }
    },
    [id],
  );

  // When processing finishes, pull the English insight + tables once.
  useEffect(() => {
    if (status === "ready") {
      loadInsight("en");
      api
        .getTables(id)
        .then((r) => setTables(r.tables || []))
        .catch(() => {});
    }
  }, [status, id, loadInsight]);

  async function handleLanguageChange(code: string) {
    setLanguage(code);
    setError(null);
    if (code === "en") {
      loadInsight("en");
      return;
    }
    setInsight(null);
    try {
      const res = await api.translateDocument(id, code);
      setInsight(res.insight);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleShare() {
    try {
      const res = await api.shareDocument(id, language);
      window.open(res.whatsapp_url, "_blank");
    } catch (err: any) {
      setError(err.message);
    }
  }

  // ---- Processing / failed states -------------------------------------
  if (status !== "ready" || !insight) {
    return (
      <main>
        <Header authed />
        <Toast message={error} onClose={() => setError(null)} />
        <div className="mx-auto flex max-w-lg flex-col items-center gap-6 px-6 py-24 text-center">
          {status === "failed" ? (
            <>
              <p className="text-lg font-semibold text-danger">
                We couldn&apos;t process this document.
              </p>
              <p className="text-ink-muted">
                The file may be corrupted or unreadable. Try uploading it again.
              </p>
              <Link href="/dashboard" className="btn-primary">
                Back to your documents
              </Link>
            </>
          ) : (
            <>
              <h1 className="font-display text-2xl font-bold text-ink">
                Reading your document…
              </h1>
              <ProgressStages stage={stage} />
              {settled && (
                <p className="text-sm text-ink-muted">Fetching the results…</p>
              )}
            </>
          )}
        </div>
      </main>
    );
  }

  // ---- Ready --------------------------------------------------------
  const eligibility = parseMaybeJson(insight.eligibility);
  const keyPoints = parseMaybeJson(insight.key_points);
  const deadlines = parseMaybeJson(insight.deadlines);

  return (
    <main>
      <Header
        authed
        right={
          <div className="flex items-center gap-2">
            <LanguageSelector value={language} onChange={handleLanguageChange} />
            <button onClick={handleShare} className="btn-ghost">
              <Share2 className="h-4 w-4" /> Share
            </button>
          </div>
        }
      />
      <Toast message={error} onClose={() => setError(null)} />

      <div className="mx-auto max-w-5xl px-6 py-8">
        <Link
          href="/dashboard"
          className="mb-6 inline-flex items-center gap-1.5 text-sm text-ink-muted hover:text-ink"
        >
          <ArrowLeft className="h-4 w-4" /> All documents
        </Link>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-6">
            <SummaryCard insight={{ ...insight, key_points: keyPoints }} />
            <EligibilityChecklist eligibility={eligibility} deadlines={deadlines} />
            <TablesCard tables={tables} />
          </div>
          <div className="lg:sticky lg:top-24 lg:self-start">
            <ChatWindow documentId={id} language={language} />
          </div>
        </div>
      </div>
    </main>
  );
}
