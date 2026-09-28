export type CurrentUser = {
  id: string;
  email: string;
  full_name: string;
  role: "ASESOR" | "SUPERVISOR" | "ADMIN";
  is_active: boolean;
};

export type Customer = {
  id: string;
  dni: string;
  first_names: string;
  last_names: string;
  phone: string;
  email: string | null;
  status: string;
  responsible_advisor_id: string | null;
};

export type Product = {
  id: string;
  code: string;
  name: string;
  category: string;
  is_active: boolean;
};

export type ProductRule = {
  id: string;
  duration_days: number;
  alert_days: number[];
  effective_from: string;
  medical_approval_reference: string;
};

export type ImportJob = {
  id: string;
  type: "customers" | "products";
  state: string;
  total_rows: number;
  valid_rows: number;
  new_rows: number;
  update_rows: number;
  rejected_rows: number;
  errors: { row_number: number | null; field: string | null; message: string }[];
};

export type Sale = { id: string; customer_id: string; sale_date: string; status: string; notes: string | null; acquisition_channel: string | null; acquisition_channel_detail: string | null; replaces_sale_id: string | null; annulment_reason: string | null; items: { id: string; product_id: string; quantity: number; purchase_type: string | null; expected_repurchase_date: string }[] };
export type Alert = { id: string; sale_item_id: string; assigned_advisor_id: string | null; alert_date: string; expected_repurchase_date: string; status: string; attempts_count: number; next_action_date: string | null; last_contact_at: string | null; closed_at: string | null };
export type AlertAttempt = { id: string; alert_id: string; contacted_at: string; channel: string; result: string; note: string | null; next_action_date: string | null };

type TokenResponse = { access_token: string };
const tokenKey = "crm_access_token";

export function getToken(): string | null { return sessionStorage.getItem(tokenKey); }
export function clearToken(): void { sessionStorage.removeItem(tokenKey); }

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body) headers.set("Content-Type", "application/json");
  const response = await fetch(path, { ...init, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? "No fue posible completar la solicitud");
  }
  return response.json() as Promise<T>;
}

export async function login(email: string, password: string): Promise<void> {
  const response = await fetch("/api/v1/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password })
  });
  if (!response.ok) throw new Error("Credenciales invalidas");
  const data = await response.json() as TokenResponse;
  sessionStorage.setItem(tokenKey, data.access_token);
}

export function getCurrentUser(): Promise<CurrentUser> { return request<CurrentUser>("/api/v1/auth/me"); }
export function listCustomers(query = ""): Promise<Customer[]> { return request<Customer[]>(`/api/v1/customers${query ? `?q=${encodeURIComponent(query)}` : ""}`); }
export function createCustomer(data: object): Promise<Customer> { return request<Customer>("/api/v1/customers", { method: "POST", body: JSON.stringify(data) }); }
export function listProducts(includeInactive = false): Promise<Product[]> { return request<Product[]>(`/api/v1/products${includeInactive ? "?include_inactive=true" : ""}`); }
export function createProduct(data: object): Promise<Product> { return request<Product>("/api/v1/products", { method: "POST", body: JSON.stringify(data) }); }
export function listRules(productId: string): Promise<ProductRule[]> { return request<ProductRule[]>(`/api/v1/products/${productId}/rules`); }
export function createRule(productId: string, data: object): Promise<ProductRule> { return request<ProductRule>(`/api/v1/products/${productId}/rules`, { method: "POST", body: JSON.stringify(data) }); }
export function listUsers(): Promise<CurrentUser[]> { return request<CurrentUser[]>("/api/v1/users"); }
export function createUser(data: object): Promise<CurrentUser> { return request<CurrentUser>("/api/v1/users", { method: "POST", body: JSON.stringify(data) }); }

export async function downloadImportTemplate(type: "customers" | "products"): Promise<void> {
  const response = await fetch(`/api/v1/imports/templates/${type}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!response.ok) throw new Error("No fue posible descargar la plantilla");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${type}_template.xlsx`;
  link.click();
  URL.revokeObjectURL(url);
}

export async function previewImport(type: "customers" | "products", file: File, allowUpdates: boolean, allowReassignment: boolean): Promise<ImportJob> {
  const body = new FormData();
  body.append("file", file);
  body.append("allow_updates", String(allowUpdates));
  body.append("allow_reassignment", String(allowReassignment));
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`/api/v1/imports/${type}/preview`, { method: "POST", headers, body });
  if (!response.ok) {
    const result = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(result?.detail ?? "No fue posible validar el archivo");
  }
  return response.json() as Promise<ImportJob>;
}

export function commitImport(jobId: string): Promise<ImportJob> {
  return request<ImportJob>(`/api/v1/imports/${jobId}/commit`, { method: "POST" });
}

export function listSales(): Promise<Sale[]> { return request<Sale[]>("/api/v1/sales"); }
export function createSale(data: object): Promise<Sale> { return request<Sale>("/api/v1/sales", { method: "POST", body: JSON.stringify(data) }); }
export function reviewDuplicate(saleId: string, decision: "APROBADA" | "RECHAZADA", reason: string): Promise<Sale> {
  return request<Sale>(`/api/v1/sales/${saleId}/duplicate-review`, { method: "POST", body: JSON.stringify({ decision, reason }) });
}
export function annulSale(saleId: string, reason: string): Promise<Sale> {
  return request<Sale>(`/api/v1/sales/${saleId}/annul`, { method: "POST", body: JSON.stringify({ reason }) });
}
export function listCustomerSales(customerId: string): Promise<Sale[]> { return request<Sale[]>(`/api/v1/customers/${customerId}/sales`); }
export function listAlerts(): Promise<Alert[]> { return request<Alert[]>("/api/v1/alerts/inbox"); }
export function listAlertAttempts(alertId: string): Promise<AlertAttempt[]> { return request<AlertAttempt[]>(`/api/v1/alerts/${alertId}/attempts`); }
export function createAlertAttempt(alertId: string, data: object): Promise<Alert> { return request<Alert>(`/api/v1/alerts/${alertId}/attempts`, { method: "POST", body: JSON.stringify(data) }); }
export function generateAlerts(runDate?: string): Promise<{ created: number; pending: number; expired: number }> { return request(`/api/v1/alerts/generate${runDate ? `?run_date=${runDate}` : ""}`, { method: "POST" }); }
