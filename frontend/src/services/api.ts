import type { Paged } from "./types";

export const apiBaseUrl = import.meta.env.VITE_API_URL || "";
let token = localStorage.getItem("recompra_token") || "";

function errorMessage(detail: unknown) {
  if (Array.isArray(detail)) {
    return detail
      .map((issue) =>
        typeof issue === "object" && issue !== null && "msg" in issue
          ? String(issue.msg)
          : String(issue),
      )
      .join(". ");
  }
  return typeof detail === "string" ? detail : "No fue posible completar la operación";
}

export function setToken(value: string) {
  token = value;
  localStorage.setItem("recompra_token", value);
}
export function clearToken() {
  token = "";
  localStorage.removeItem("recompra_token");
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(errorMessage(body.detail));
  }
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

export async function upload<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${apiBaseUrl}/api/v1${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(errorMessage(payload.detail));
  }
  return response.json() as Promise<T>;
}

export async function listAll<T>(path: string, pageSize = 100): Promise<T[]> {
  const separator = path.includes("?") ? "&" : "?";
  const first = await api<Paged<T> | T[]>(`${path}${separator}page=1&page_size=${pageSize}`);
  if (Array.isArray(first) || first.pages <= 1) return Array.isArray(first) ? first : first.items;

  const pages = await Promise.all(
    Array.from({ length: first.pages - 1 }, (_, index) =>
      api<Paged<T>>(`${path}${separator}page=${index + 2}&page_size=${pageSize}`),
    ),
  );
  return [...first.items, ...pages.flatMap((page) => page.items)];
}

export async function download(path: string, filename: string) {
  const response = await fetch(`${apiBaseUrl}/api/v1${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) throw new Error(errorMessage((await response.json().catch(() => ({}))).detail));
  const link = document.createElement("a");
  link.href = URL.createObjectURL(await response.blob());
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 0);
}
