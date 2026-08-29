"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Brand } from "@/components/Brand";
import { api } from "@/lib/api-client";

export function Header({
  authed = false,
  right,
}: {
  authed?: boolean;
  right?: React.ReactNode;
}) {
  const router = useRouter();

  async function handleLogout() {
    await api.logout();
    router.push("/");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-20 border-b border-line/80 bg-paper/85 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
        <Brand />
        <div className="flex items-center gap-3">
          {right}
          {authed && (
            <button onClick={handleLogout} className="btn-ghost">
              <LogOut className="h-4 w-4" /> Sign out
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
