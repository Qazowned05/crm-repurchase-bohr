export type Role = "ASESOR" | "SUPERVISOR" | "ADMIN";
export type Paged<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};
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
export type RepurchaseItem = {
  product_id: string;
  quantity: number;
  unit_price: number;
};
export type AlertRepurchaseCreate = {
  sale_date?: string;
  notes?: string;
  acquisition_channel?: "TV" | "DIGITAL" | "OTROS";
  acquisition_channel_detail?: string;
  items: RepurchaseItem[];
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
  assigned_advisor_name?: string | null;
  assigned_advisor_email?: string | null;
  alert_date: string;
  expected_repurchase_date: string;
  status: string;
  attempts_count: number;
  next_action_date?: string | null;
  customer_id?: string | null;
  customer_dni?: string | null;
  customer_first_names?: string | null;
  customer_last_names?: string | null;
  customer_phone?: string | null;
  customer_email?: string | null;
  product_id?: string | null;
  product_code?: string | null;
  product_name?: string | null;
  product_brand?: string | null;
  product_category?: string | null;
  original_sale_id?: string | null;
  original_sale_date?: string | null;
  seller_advisor_id?: string | null;
  seller_advisor_name?: string | null;
  seller_advisor_email?: string | null;
};
export type ContactAttempt = {
  id: string;
  alert_id: string;
  advisor_id: string;
  contacted_at: string;
  channel: string;
  result: string;
  note?: string | null;
  next_action_date?: string | null;
  observation?: string | null;
  user_name?: string | null;
  parent_typification_name?: string | null;
  child_typification_name?: string | null;
};
export type ManagedAlert = Alert & {
  last_contact_at?: string | null;
  closed_at?: string | null;
  closure_reason?: string | null;
  contact_attempts: ContactAttempt[];
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
  unit_price?: string | null;
  purchase_type?: string | null;
  product_code?: string | null;
  product_name?: string | null;
  product_brand?: string | null;
  product_category?: string | null;
};
export type Sale = {
  id: string;
  customer_id: string;
  advisor_id: string;
  sale_date: string;
  notes?: string | null;
  status: string;
  acquisition_channel?: string | null;
  acquisition_channel_detail?: string | null;
  customer_dni?: string | null;
  customer_first_names?: string | null;
  customer_last_names?: string | null;
  customer_phone?: string | null;
  customer_email?: string | null;
  advisor_full_name?: string | null;
  advisor_email?: string | null;
  items: SaleItem[];
};
export type AdvisorSalesMetrics = {
  confirmed_sales: number;
  confirmed_items: number;
  repurchase_sales: number;
  repurchase_items: number;
};
export type AdvisorRanking = {
  advisor_id: string;
  advisor_name: string;
  confirmed_repurchases: number;
  managed_alerts: number;
  contact_attempts: number;
  closed_alerts: number;
};
export type AttentionTypification = {
  typification_id: string;
  typification_code: string;
  typification_name: string;
  attempts: number;
};
export type Metrics = {
  alerts_considered: number;
  contact_rate: number;
  repurchase_rate: number;
  repurchase_denominator: number;
  average_days_between_purchases?: number | null;
  advisor_ranking: AdvisorRanking[];
  attention_typifications: AttentionTypification[];
};
