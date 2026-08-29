"use client";

import Link from "next/link";
import { FileText, Languages, MessagesSquare, ListChecks } from "lucide-react";
import { Header } from "@/components/Header";
import { useIsAuthed } from "@/lib/useAuth";

const STEPS = [
  {
    icon: FileText,
    title: "Upload anything",
    body: "A scheme notice, a form, an official letter — as a PDF or just a photo of the page.",
  },
  {
    icon: ListChecks,
    title: "Get the essentials",
    body: "A plain-language summary, who can apply, the documents you need, and every key date.",
  },
  {
    icon: MessagesSquare,
    title: "Ask questions",
    body: "“Am I eligible?” “What's the deadline?” — answered only from your document.",
  },
  {
    icon: Languages,
    title: "In your language",
    body: "Read all of it in Hindi, Kannada, Tamil, Telugu, Marathi or Bengali.",
  },
];

export default function LandingPage() {
  const authed = useIsAuthed();

  return (
    <main>
      <Header
        authed={authed}
        right={
          !authed && (
            <Link href="/login" className="btn-primary">
              Sign in
            </Link>
          )
        }
      />

      <section className="mx-auto max-w-3xl px-6 pb-16 pt-16 text-center sm:pt-24">
        <p className="inline-flex items-center gap-2 rounded-pill border border-line bg-paper-raised px-3 py-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">
          Government paperwork, decoded
        </p>
        <h1 className="mt-6 font-display text-4xl font-bold leading-[1.1] text-ink sm:text-6xl">
          Understand any government
          <br />
          document in <span className="text-teal">plain language</span>.
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-ink-soft">
          Parchi turns a dense notice into a clear summary, an eligibility
          checklist, the dates that matter, and a chat that answers your
          questions — in the language you read.
        </p>
        <div className="mt-9 flex items-center justify-center gap-3">
          <Link href={authed ? "/dashboard" : "/login"} className="btn-primary px-6 py-3 text-base">
            {authed ? "Go to your documents" : "Get started — it's free"}
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-24">
        <div className="grid gap-4 sm:grid-cols-2">
          {STEPS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="card p-6">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-teal-wash text-teal">
                <Icon className="h-5 w-5" />
              </span>
              <h3 className="mt-4 font-display text-lg font-bold text-teal-dark">{title}</h3>
              <p className="mt-1.5 text-[15px] leading-relaxed text-ink-soft">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
