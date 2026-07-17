"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { Share2 } from "lucide-react";
import { api } from "@/lib/api-client";
import { SummaryCard } from "@/components/SummaryCard";
import { EligibilityChecklist } from "@/components/EligibilityChecklist";
import { ChatWindow } from "@/components/ChatWindow";
import { LanguageSelector } from "@/components/LanguageSelector";

const STAGES = ["Reading document…", "Simplifying…", "Almost ready…"];

export default function DocumentPage() {
  const { id } = useParams<{ id: string }>();
  const [status, setStatus] = useState<string>("processing");
  const [insight, setInsight] = useState<any>(null);
  const [language, setLanguage] = useState("en");
  const [stageIndex, setStageIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const poll = useCallback(async () => {
    try {
      const res = await api.getDocument(id, language);
      setStatus(res.document.status);
      if (res.insight) setInsight(res.insight);
    } catch (err: any) {
      setError(err.message);
    }
  }, [id, language]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, 3000);
    const stageTimer = setInterval(() => setStageIndex((i) => (i + 1) % STAGES.length), 2500);
    return () => {
      clearInterval(interval);
      clearInterval(stageTimer);
    };
  }, [poll]);

  async function handleLanguageChange(code: string) {
    setLanguage(code);
    if (code === "en") {
      poll();
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
    const res = await api.shareDocument(id, language);
    window.open(res.whatsapp_url, "_blank");
  }

  if (status !== "ready" || !insight) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-paper px-6 text-center">
        {status === "failed" ? (
          <p className="text-lg text-red-600">
            Something went wrong while processing this document. Please try uploading it again.
          </p>
        ) : (
          <>
            <div className="h-12 w-12 animate-spin rounded-full border-4 border-teal/20 border-t-teal" />
            <p className="text-lg text-ink/70">{STAGES[stageIndex]}</p>
          </>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </main>
    );
  }

  const eligibility = typeof insight.eligibility === "string" ? JSON.parse(insight.eligibility) : insight.eligibility;
  const keyPoints = typeof insight.key_points === "string" ? JSON.parse(insight.key_points) : insight.key_points;
  const deadlines = typeof insight.deadlines === "string" ? JSON.parse(insight.deadlines) : insight.deadlines;

  return (
    <main className="min-h-screen bg-paper pb-16">
      <div className="sticky top-0 z-10 flex items-center justify-between border-b border-ink/10 bg-paper/95 px-6 py-5 backdrop-blur">
        <span className="font-display text-5xl font-bold tracking-tight text-teal-dark">SARAL</span>
        <div className="flex items-center gap-3">
          <LanguageSelector value={language} onChange={handleLanguageChange} />
          <button
            onClick={handleShare}
            className="flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-teal-dark shadow-sm hover:bg-teal/10"
          >
            <Share2 className="h-4 w-4" /> Share
          </button>
        </div>
      </div>

      <div className="mx-auto grid max-w-5xl gap-6 px-6 py-8 md:grid-cols-2">
        <div className="space-y-6">
          <SummaryCard insight={{ ...insight, key_points: keyPoints }} />
          <EligibilityChecklist eligibility={eligibility} deadlines={deadlines} />
        </div>
        <div>
          <ChatWindow documentId={id} language={language} />
        </div>
      </div>
    </main>
  );
}