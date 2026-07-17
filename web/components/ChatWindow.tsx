"use client";

import { useEffect, useRef, useState } from "react";
import { Send, MessageCircle } from "lucide-react";
import { api } from "@/lib/api-client";

type Message = { role: "user" | "assistant"; content: string };

export function ChatWindow({ documentId, language }: { documentId: string; language: string }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getChatHistory(documentId).then((res) => setMessages(res.messages || []));
  }, [documentId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function send() {
    if (!input.trim() || sending) return;
    const question = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setSending(true);
    try {
      const res = await api.sendChatMessage(documentId, question, language);
      setMessages((prev) => [...prev, { role: "assistant", content: res.answer }]);
    } catch (err: any) {
      setMessages((prev) => [...prev, { role: "assistant", content: `Something went wrong: ${err.message}` }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex h-[32rem] flex-col rounded-3xl bg-white shadow-sm">
      <div className="flex items-center gap-2 border-b border-ink/10 px-6 py-4">
        <MessageCircle className="h-5 w-5 text-teal" />
        <h2 className="font-display text-xl font-bold text-teal-dark">Ask a question</h2>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-6 py-4">
        {messages.length === 0 && (
          <p className="text-base text-ink/50">
            Ask anything about this document — e.g. &quot;Am I eligible?&quot; or &quot;What&apos;s the deadline?&quot;
          </p>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-2xl px-4 py-3 text-base leading-relaxed ${
              m.role === "user" ? "ml-auto bg-teal text-white" : "bg-paper text-ink"
            }`}
          >
            {m.content}
          </div>
        ))}
        {sending && <div className="max-w-[85%] rounded-2xl bg-paper px-4 py-3 text-base text-ink/50">Thinking…</div>}
      </div>

      <div className="flex items-center gap-2 border-t border-ink/10 p-4">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Type your question…"
          className="flex-1 rounded-full border-2 border-teal/20 px-4 py-3 text-base focus:border-teal"
        />
        <button
          onClick={send}
          disabled={sending}
          className="rounded-full bg-amber p-3 text-white hover:bg-amber-dark disabled:opacity-50"
          aria-label="Send question"
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}