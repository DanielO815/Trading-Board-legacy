// frontend/src/api.js
// Minimaler API-Helper (nicht übertrieben, aber sauberer als überall fetch-Strings)
// Unterstützt beide ENV-Varianten, damit es nicht "schwarzer Screen" wird:
// - VITE_API_URL (empfohlen)
// - VITE_API_BASE (alt)
const rawBase =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE ||
  "http://127.0.0.1:8000";

export const API_BASE = String(rawBase).replace(/\/$/, "");

function toUrl(path) {
  if (!path) return API_BASE;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${API_BASE}${path}`;
  return `${API_BASE}/${path}`;
}

async function request(path, options = {}) {
  const res = await fetch(toUrl(path), options);

  const ct = (res.headers.get("content-type") || "").toLowerCase();
  let payload;
  try {
    payload = ct.includes("application/json") ? await res.json() : await res.text();
  } catch {
    payload = null;
  }

  if (!res.ok) {
    const detail =
      typeof payload === "string"
        ? payload
        : payload && typeof payload === "object"
        ? payload.detail || JSON.stringify(payload)
        : "";
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }

  return payload;
}

export function apiGet(path, { signal } = {}) {
  return request(path, { method: "GET", signal });
}

export function apiPost(path, body, { signal } = {}) {
  const hasBody = body !== undefined;
  return request(path, {
    method: "POST",
    signal,
    headers: hasBody ? { "Content-Type": "application/json" } : undefined,
    body: hasBody ? JSON.stringify(body) : undefined,
  });
}
