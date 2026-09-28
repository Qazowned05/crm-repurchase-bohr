const baseUrl = import.meta.env.VITE_API_URL || ""
let token = localStorage.getItem("recompra_token") || ""

export function setToken(value: string) { token = value; localStorage.setItem("recompra_token", value) }
export function clearToken() { token = ""; localStorage.removeItem("recompra_token") }
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${baseUrl}/api/v1${path}`, {
    ...options, headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers },
  })
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail || "No fue posible completar la operación") }
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}
