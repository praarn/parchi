"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setToken } from "@/lib/api-client";
import { UploadDropzone } from "@/components/UploadDropzone";

export default function HomePage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function handleAuth(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = mode === "login" ? await api.login(email, password) : await api.signup(email, password, name);
      setToken(res.token);
      setAuthed(true);
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      const { document } = await api.uploadDocument(file);
      await api.processDocument(document.id);
      router.push(`/document/${document.id}`);
    } catch (err: any) {
      setError(err.message);
      setUploading(false);
    }
  }

  return (
    <main className="min-h-screen bg-paper">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-10">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-5xl font-bold tracking-tight text-teal-dark">SARAL</span>
          <span className="text-base text-ink/50">सरल · simple</span>
        </div>
      </header>

      <section className="mx-auto max-w-3xl px-6 pb-24 pt-8 text-center">
        <h1 className="font-display text-4xl font-bold leading-tight text-ink sm:text-5xl">
          Government paperwork,
          <br />
          <span className="text-teal">explained in plain language.</span>
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-lg text-ink/70">
          Upload any scheme notice, form, or government letter. Get a summary, an
          eligibility checklist, and answers to your questions — in your language.
        </p>

        <div className="mt-10">
          {!authed ? (
            <form onSubmit={handleAuth} className="mx-auto max-w-sm space-y-3 rounded-3xl bg-white p-6 text-left shadow-sm">
              <h2 className="text-center font-display text-xl font-bold text-teal-dark">
                {mode === "login" ? "Log in to continue" : "Create your account"}
              </h2>
              {mode === "signup" && (
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="w-full rounded-xl border-2 border-teal/20 px-4 py-3 text-base focus:border-teal"
                />
              )}
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                className="w-full rounded-xl border-2 border-teal/20 px-4 py-3 text-base focus:border-teal"
              />
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full rounded-xl border-2 border-teal/20 px-4 py-3 text-base focus:border-teal"
              />
              {error && <p className="text-sm text-red-600">{error}</p>}
              <button type="submit" className="w-full rounded-full bg-teal py-3 font-semibold text-white hover:bg-teal-dark">
                {mode === "login" ? "Log in" : "Sign up"}
              </button>
              <button
                type="button"
                onClick={() => setMode(mode === "login" ? "signup" : "login")}
                className="w-full text-center text-sm text-teal-dark underline"
              >
                {mode === "login" ? "New here? Create an account" : "Already have an account? Log in"}
              </button>
            </form>
          ) : uploading ? (
            <p className="text-lg text-ink/70">Uploading and starting processing…</p>
          ) : (
            <UploadDropzone onFileSelected={handleFile} />
          )}
          {error && authed && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </div>
      </section>
    </main>
  );
}