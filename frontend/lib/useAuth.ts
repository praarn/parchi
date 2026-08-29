"use client";

import { useSyncExternalStore } from "react";
import { isAuthed, subscribeAuth } from "@/lib/api-client";

/** Reactive auth state — updates on sign-in/out in this tab and others. */
export function useIsAuthed(): boolean {
  return useSyncExternalStore(
    subscribeAuth,
    () => isAuthed(),
    () => false,
  );
}
