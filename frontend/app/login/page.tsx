"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/Header";
import { AuthForm } from "@/components/AuthForm";
import { isAuthed } from "@/lib/api-client";

export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    if (isAuthed()) router.replace("/dashboard");
  }, [router]);

  return (
    <main>
      <Header />
      <section className="mx-auto flex max-w-5xl flex-col items-center px-6 py-16">
        <h1 className="mb-2 font-display text-3xl font-bold text-ink">Sign in to Parchi</h1>
        <p className="mb-8 text-ink-muted">Your documents stay private to your account.</p>
        <AuthForm redirectTo="/dashboard" />
      </section>
    </main>
  );
}
