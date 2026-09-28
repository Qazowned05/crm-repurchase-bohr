export type Role = "ASESOR" | "SUPERVISOR" | "ADMIN";
export type User = { id: string; email: string; full_name: string; role: Role; is_active: boolean };
export type Customer = {
  id: string;
  dni: string;
  first_names: string;
  last_names: string;
  phone: string;
  email?: string;
  status: string;
  responsible_advisor_id?: string | null;
  acquisition_channel?: string | null;
  condition?: string | null;
  birth_year?: number | null;
  sales_district?: string | null;
};
export type CatalogItem = {
  id: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};
export type Product = {
  id: string;
  code: string;
  name: string;
  brand_id: string;
  category_id: string;
  brand_name: string;
  category_name: string;
  is_active: boolean;
};
export type ProductRepurchaseRule = {
  id: string;
  product_id: string;
  duration_days: number;
  alert_days: number[];
  effective_from: string;
  created_by_user_id: string;
  created_at: string;
};
export type Alert = {
  id: string;
  assigned_advisor_id?: string | null;
  alert_date: string;
  expected_repurchase_date: string;
  status: string;
  attempts_count: number;
  next_action_date?: string | null;
};
export type Typification = {
  id: string;
  parent_id?: string | null;
  code: string;
  name: string;
  is_active: boolean;
  requires_next_action: boolean;
  requires_note: boolean;
  requires_close: boolean;
};
export type TypificationTree = Typification & { children: TypificationTree[] };
export type RecoveryAlert = Alert & {
  sale_id: string;
  sale_date: string;
  product_id: string;
  product_code: string;
  product_name: string;
  latest_contact_typification?: string | null;
  latest_contact_date?: string | null;
};
export type RecoveryCustomer = {
  customer_id: string;
  dni: string;
  first_names: string;
  last_names: string;
  phone: string;
  alerts: RecoveryAlert[];
};
export type SaleItem = {
  id: string;
  product_id: string;
  quantity: number;
  purchase_type?: string | null;
};
export type Sale = {
  id: string;
  customer_id: string;
  advisor_id: string;
  sale_date: string;
  notes?: string | null;
  status: string;
  items: SaleItem[];
};
export type AdvisorSalesMetrics = {
  confirmed_sales: number;
  confirmed_items: number;
  repurchase_sales: number;
  repurchase_items: number;
};
export type AlertGeneration = {
  run_date: string;
  created: number;
  pending: number;
  expired: number;
};
