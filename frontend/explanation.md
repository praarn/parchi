# frontend/ — why it's built this way

Next.js 16 (App Router) + TypeScript + Tailwind. No component library — the
design system is a handful of `@layer components` classes in `app/globals.css`
(`.card`, `.btn-primary`, `.input`, …) plus tokens in `tailwind.config.ts`.

## Routes

| route | purpose |
|-------|---------|
| `/` | landing — what Parchi does, one CTA |
| `/login` | sign in / sign up (`components/AuthForm.tsx`) |
| `/dashboard` | upload zone, usage stats, list of your documents |
| `/document/[id]` | live processing progress, then summary + eligibility + tables + chat |

## Key pieces

**`lib/api-client.ts`** — the only place that talks to the API. Holds the access
+ refresh tokens in `localStorage`, attaches the bearer token, and on a `401`
transparently calls `/auth/refresh` once and retries. Reads FastAPI's `{detail}`
error shape (string or validation array).

**`lib/useAuth.ts`** — `useIsAuthed()` via `useSyncExternalStore`, so sign-in and
sign-out (including in another tab) update the UI without an effect.

**`lib/useDocumentProgress.ts`** — opens a WebSocket to
`/ws/documents/{id}` for live stage updates while a document processes, and
**falls back to polling** `GET /documents/{id}` if the socket can't connect or
drops. Either way it settles on `ready` / `failed`. `components/ProgressStages`
renders it as a checklist.

**Theme** — the original warm "civic paper" look (bone paper, deep teal, amber
accent, Fraunces + Inter), kept but tightened: real ink/paper shades so surfaces
layer, a radius + shadow scale, focus-visible rings, and `prefers-reduced-motion`
honoured.

## Docker

Multi-stage build → `output: "standalone"`, so the runtime image is just
`node server.js` + the standalone bundle. `NEXT_PUBLIC_*` is inlined at build
time, so the API URL is passed as a **build arg** in `docker-compose.yml`, not a
runtime env var.
