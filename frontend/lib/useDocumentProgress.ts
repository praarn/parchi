"use client";

import { useEffect, useRef, useState } from "react";
import { api, documentWsUrl } from "@/lib/api-client";

export type ProgressState = {
  status: string;
  stage: string | null;
};

/**
 * Live document-processing progress.
 *
 * Opens a WebSocket to the API and updates on every stage change the worker
 * pushes. If the socket can't connect (or drops), it transparently falls back
 * to polling `GET /documents/:id` every few seconds. Either way it settles once
 * the document reaches `ready` / `failed`.
 */
export function useDocumentProgress(id: string, initial: ProgressState) {
  const [state, setState] = useState<ProgressState>(initial);
  const settled = state.status === "ready" || state.status === "failed";
  const stateRef = useRef(state);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    if (!id) return;
    let closed = false;
    let ws: WebSocket | null = null;
    let poll: ReturnType<typeof setInterval> | null = null;

    const apply = (next: Partial<ProgressState>) => {
      setState((prev) => ({ ...prev, ...next }));
    };

    const startPolling = () => {
      if (poll) return;
      poll = setInterval(async () => {
        try {
          const res = await api.getDocument(id);
          apply({
            status: res.document.status,
            stage: res.document.processing_stage ?? null,
          });
          if (["ready", "failed"].includes(res.document.status) && poll) {
            clearInterval(poll);
            poll = null;
          }
        } catch {
          /* keep trying */
        }
      }, 2500);
    };

    try {
      ws = new WebSocket(documentWsUrl(id));
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          apply({
            status: msg.status ?? stateRef.current.status,
            stage: msg.stage ?? null,
          });
        } catch {
          /* ignore malformed frame */
        }
      };
      ws.onerror = () => startPolling();
      ws.onclose = () => {
        if (
          !closed &&
          !["ready", "failed"].includes(stateRef.current.status)
        ) {
          startPolling();
        }
      };
    } catch {
      startPolling();
    }

    return () => {
      closed = true;
      ws?.close();
      if (poll) clearInterval(poll);
    };
  }, [id]);

  return { ...state, settled };
}
