/**
 * Thin fetch wrapper for the VisionDecor backend.
 *
 * Auth (decision D014): the JWT lives in an httpOnly cookie the browser
 * sends automatically (`credentials: "include"`) — this client never reads
 * or stores it. State-changing requests must echo the CSRF cookie's value
 * in an X-CSRF-Token header (double-submit pattern); this file is the only
 * place that logic lives, so every caller gets it for free.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000";

export class ApiError extends Error {
  code: string;
  status: number;
  details?: Record<string, unknown>;

  constructor(code: string, message: string, status: number, details?: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; isFormData?: boolean } = {}
): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};

  if (!options.isFormData && options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (!SAFE_METHODS.has(method)) {
    const csrfToken = readCookie("vd_csrf_token");
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    credentials: "include", // sends the httpOnly auth cookie + CSRF cookie
    body: options.isFormData
      ? (options.body as FormData)
      : options.body !== undefined
      ? JSON.stringify(options.body)
      : undefined,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : null;

  if (!response.ok) {
    const err = payload?.error ?? { code: "unknown_error", message: "Something went wrong." };
    throw new ApiError(err.code, err.message, response.status, err.details);
  }
  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  postForm: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData, isFormData: true }),
};
