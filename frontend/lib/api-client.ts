const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || API_URL.replace(/^http/, "ws");

const ACCESS_KEY = "parchi_access";
const REFRESH_KEY = "parchi_refresh";

// ---------------------------------------------------------------------------
// Token storage. Access token is short-lived; both are kept in localStorage so
// a page reload stays signed in. A 401 transparently triggers one refresh +
// retry before the error surfaces.
// ---------------------------------------------------------------------------

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ACCESS_KEY);
}
function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(REFRESH_KEY);
}
export function setTokens(t: { access_token: string; refresh_token: string }) {
  window.localStorage.setItem(ACCESS_KEY, t.access_token);
  window.localStorage.setItem(REFRESH_KEY, t.refresh_token);
  notifyAuthChange();
}
export function clearTokens() {
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  notifyAuthChange();
}
export function isAuthed(): boolean {
  return !!getAccessToken();
}

const authListeners = new Set<() => void>();
function notifyAuthChange() {
  authListeners.forEach((fn) => fn());
}
/** Subscribe to sign-in/sign-out (this tab and other tabs). */
export function subscribeAuth(cb: () => void): () => void {
  authListeners.add(cb);
  if (typeof window !== "undefined") window.addEventListener("storage", cb);
  return () => {
    authListeners.delete(cb);
    if (typeof window !== "undefined") window.removeEventListener("storage", cb);
  };
}

function parseError(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg);
  }
  return `Request failed (${status})`;
}

let refreshInFlight: Promise<boolean> | null = null;

async function tryRefresh(): Promise<boolean> {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token }),
        });
        if (!res.ok) {
          clearTokens();
          return false;
        }
        setTokens(await res.json());
        return true;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

async function request<T = any>(
  path: string,
  options: RequestInit = {},
  allowRetry = true,
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401 && allowRetry && (await tryRefresh())) {
    return request<T>(path, options, false);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(parseError(body, res.status));
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function documentWsUrl(id: string): string {
  const token = getAccessToken() ?? "";
  return `${WS_URL}/ws/documents/${id}?token=${encodeURIComponent(token)}`;
}

export const api = {
  signup: (email: string, password: string, name?: string) =>
    request("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password, name }),
    }),

  login: (email: string, password: string) =>
    request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  logout: async () => {
    const refresh_token = getRefreshToken();
    if (refresh_token) {
      await request("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token }),
      }).catch(() => {});
    }
    clearTokens();
  },

  me: () => request("/auth/me"),

  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request("/documents/upload", { method: "POST", body: form });
  },

  processDocument: (id: string) =>
    request(`/documents/${id}/process`, { method: "POST" }),

  getDocument: (id: string, language = "en") =>
    request(`/documents/${id}?language=${language}`),

  listDocuments: (opts: { limit?: number; offset?: number } = {}) => {
    const params = new URLSearchParams();
    if (opts.limit != null) params.set("limit", String(opts.limit));
    if (opts.offset != null) params.set("offset", String(opts.offset));
    const qs = params.toString();
    return request(`/documents${qs ? `?${qs}` : ""}`);
  },

  getStats: () => request(`/documents/stats`),

  getTables: (id: string) => request(`/documents/${id}/tables`),

  translateDocument: (id: string, language: string) =>
    request(`/documents/${id}/translate`, {
      method: "POST",
      body: JSON.stringify({ language }),
    }),

  shareDocument: (id: string, language = "en") =>
    request(`/documents/${id}/share?language=${language}`, { method: "POST" }),

  sendChatMessage: (id: string, message: string, language = "en") =>
    request(`/documents/${id}/chat`, {
      method: "POST",
      body: JSON.stringify({ message, language }),
    }),

  getChatHistory: (id: string) => request(`/documents/${id}/chat`),
};
