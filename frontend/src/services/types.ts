export type Role = "ASESOR" | "SUPERVISOR" | "ADMIN"
export type User = { id: string; email: string; full_name: string; role: Role; is_active: boolean }
export type Customer = { id: string; dni: string; first_names: string; last_names: string; phone: string; email?: string; status: string; responsible_advisor_id?: string | null; acquisition_channel?: string | null; condition?: string | null; birth_year?: number | null; sales_district?: string | null }
export type Product = { id: string; code: string; name: string; category: string; is_active: boolean }
export type Alert = { id: string; assigned_advisor_id?: string | null; alert_date: string; expected_repurchase_date: string; status: string; attempts_count: number; next_action_date?: string | null }
export type Typification = { id: string; code: string; name: string; is_active: boolean; requires_next_action: boolean; requires_note: boolean; requires_close: boolean }
export type RecoveryCustomer = { customer_id: string; dni: string; first_names: string; last_names: string; phone: string; alerts: Array<Alert & { sale_id: string; sale_date: string; product_id: string; product_code: string; product_name: string }> }
