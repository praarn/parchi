"use client";

import { useEffect, useRef, useState } from "react";
import { Send, MessageCircleQuestion } from "lucide-react";
import { api } from "@/lib/api-client";

type Message = { role: "user" | "assistant"; content: string; sources?: number[] };

const SUGGESTIONS = ["Am I eligible?", "What documents do I need?", "What's the deadline?"];

export function ChatWindow({
  documentId,
  language,
}: {
  documentId: string;
  language: string;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .getChatHistory(documentId)
      .then((res) => setMessages(res.messages || []))
      .catch(() => {});
  }, [documentId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send(text?: string) {
    const question = (text ?? input).trim();
    if (!question || sending) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setSending(true);
    try {
      const res = await api.sendChatMessage(documentId, question, language);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.answer, sources: res.sources },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Something went wrong: ${err.message}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="card flex h-[34rem] flex-col">
      <div className="flex items-center gap-2 border-b border-line px-5 py-4">
        <MessageCircleQuestion className="h-5 w-5 text-teal" />
        <h2 className="font-display text-lg font-bold text-teal-dark">Ask about this document</h2>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-ink-muted">
              Answers come only from this document — nothing made up.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-pill border border-line bg-paper px-3 py-1.5 text-xs font-medium text-ink-soft hover:border-teal hover:text-teal-dark"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed ${
              m.role === "user"
                ? "ml-auto bg-teal text-white"
                : "border border-line bg-paper text-ink"
            }`}
          >
            {m.content}
            {m.sources && m.sources.length > 0 && (
              <span className="mt-1 block text-xs opacity-70">
                Source: page {m.sources.join(", ")}
              </span>
            )}
          </div>
        ))}
        {sending && (
          <div className="max-w-[85%] rounded-2xl border border-line bg-paper px-4 py-2.5 text-sm text-ink-muted">
            Thinking…
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-line p-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Type your question…"
          className="input flex-1 rounded-pill"
        />
        <button
          onClick={() => send()}
          disabled={sending}
          className="btn bg-amber p-3 text-white hover:bg-amber-dark"
          aria-label="Send question"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </section>
  );
}
