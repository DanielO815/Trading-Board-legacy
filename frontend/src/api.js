/**
 * API-Helper-Modul für HTTP-Kommunikation mit Backend.
 * 
 * Bietet Funktionen für GET und POST Anfragen mit automatischer
 * URL-Konstruktion, Error-Handling und Inhaltstyp-Verarbeitung.
 */

// Frontend: src/api.js
// Minimaler API-Helper (nicht übertrieben, aber sauberer als überall fetch-Strings)
// Unterstützt beide ENV-Varianten, damit es nicht "schwarzer Screen" wird:
// - VITE_API_URL (empfohlen)
// - VITE_API_BASE (alt)
const rawBase =
  import.meta.env.VITE_API_URL ||
  import.meta.env.VITE_API_BASE ||
  "http://127.0.0.1:8000";

/**
 * Basis-URL für Backend-API.
 * @type {string}
 */
export const API_BASE = String(rawBase).replace(/\/$/, "");

/**
 * Konvertiert relativen oder absoluten Pfad zu vollständiger API-URL.
 * 
 * @param {string} path - API-Pfad (z.B. "/api/btc/price")
 * @returns {string} Vollständige URL für API-Anfrage
 */
function toUrl(path) {
  if (!path) return API_BASE;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${API_BASE}${path}`;
  return `${API_BASE}/${path}`;
}

/**
 * Führt HTTP-Anfrage aus mit automatischer Error-Behandlung.
 * 
 * Parst JSON oder Text-Antwort basierend auf Content-Type Header.
 * Wirft Error mit Status und Detail-Nachricht bei fehlgeschlagenen Anfragen.
 * 
 * @async
 * @param {string} path - API-Pfad
 * @param {Object} [options={}] - Fetch-Optionen (method, headers, body, signal)
 * @returns {Promise<any>} Geparste Antwort (JSON oder Text)
 * @throws {Error} Bei HTTP-Fehler mit Status und Detail-Nachricht
 */
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

/**
 * Führt GET-Anfrage gegen Backend-API aus.
 * 
 * @async
 * @param {string} path - API-Pfad (z.B. "/api/btc/price")
 * @param {Object} [options={}] - Zusätzliche Optionen (z.B. signal für AbortController)
 * @returns {Promise<any>} Geparste Antwort vom Backend
 */
export function apiGet(path, { signal } = {}) {
  return request(path, { method: "GET", signal });
}

/**
 * Führt POST-Anfrage gegen Backend-API mit JSON-Body aus.
 * 
 * @async
 * @param {string} path - API-Pfad (z.B. "/api/export/coinbase/start")
 * @param {any} body - Request-Body (wird zu JSON konvertiert)
 * @param {Object} [options={}] - Zusätzliche Optionen (z.B. signal für AbortController)
 * @returns {Promise<any>} Geparste Antwort vom Backend
 */
export function apiPost(path, body, { signal } = {}) {
  const hasBody = body !== undefined;
  return request(path, {
    method: "POST",
    signal,
    headers: hasBody ? { "Content-Type": "application/json" } : undefined,
    body: hasBody ? JSON.stringify(body) : undefined,
  });
}
