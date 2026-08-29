"use client";

import { useEffect } from "react";
import { AlertCircle, X } from "lucide-react";

/** Minimal error toast, bottom-centre, auto-dismisses. */
export function Toast({
  message,
  onClose,
}: {
  message: string | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onClose, 6000);
    return () => clearTimeout(t);
  }, [message, onClose]);

  if (!message) return null;
  return (
    <div className="fixed inset-x-0 bottom-6 z-50 flex justify-center px-4">
      <div
        role="alert"
        className="flex items-start gap-3 rounded-card border border-danger/20 bg-paper-raised px-4 py-3 text-sm text-ink shadow-lift"
      >
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
        <span className="max-w-sm">{message}</span>
        <button onClick={onClose} aria-label="Dismiss" className="text-ink-muted hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
