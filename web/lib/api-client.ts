const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("saral_token");
}

export function setToken(token: string) {
  window.localStorage.setItem("saral_token", token);
}

export function clearToken() {
  window.localStorage.removeItem("saral_token");
}

async function request(path: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  signup: (email: string, password: string, name: string) =>
    request("/auth/signup", { method: "POST", body: JSON.stringify({ email, password, name }) }),

  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),

  uploadDocument: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request("/documents/upload", { method: "POST", body: form });
  },

  processDocument: (id: string) => request(`/documents/${id}/process`, { method: "POST" }),

  getDocument: (id: string, language = "en") => request(`/documents/${id}?language=${language}`),

  listDocuments: () => request("/documents"),

  translateDocument: (id: string, language: string) =>
    request(`/documents/${id}/translate`, { method: "POST", body: JSON.stringify({ language }) }),

  shareDocument: (id: string, language = "en") =>
    request(`/documents/${id}/share?language=${language}`, { method: "POST" }),

  sendChatMessage: (id: string, message: string, language = "en") =>
    request(`/documents/${id}/chat`, { method: "POST", body: JSON.stringify({ message, language }) }),

  getChatHistory: (id: string) => request(`/documents/${id}/chat`),
};