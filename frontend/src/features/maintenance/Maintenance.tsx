import { useEffect, useState } from "react"
import { CrudModal } from "../../components/CrudModal"
import { api } from "../../services/api"
import type { Customer, Product, User } from "../../services/types"
type Kind = "customers" | "products" | "users"
const definitions = {
  customers: { title: "Clientes", fields: [{ name: "dni", label: "DNI", required: true }, { name: "first_names", label: "Nombres", required: true }, { name: "last_names", label: "Apellidos", required: true }, { name: "phone", label: "Teléfono", required: true }, { name: "email", label: "Correo", type: "email" }, { name: "condition", label: "Enfermedad o condición" }, { name: "birth_year", label: "Año de nacimiento", type: "number" }, { name: "sales_district", label: "Distrito de venta" }] },
  products: { title: "Productos", fields: [{ name: "code", label: "Código", required: true }, { name: "name", label: "Nombre", required: true }, { name: "category", label: "Categoría", required: true }, { name: "is_active", label: "Activo", type: "checkbox" }] },
  users: { title: "Usuarios", fields: [{ name: "email", label: "Correo", type: "email", required: true }, { name: "full_name", label: "Nombre completo", required: true }, { name: "password", label: "Contraseña", type: "password", required: true }, { name: "role", label: "Rol", required: true, options: [{ value: "ASESOR", label: "Asesor" }, { value: "SUPERVISOR", label: "Supervisor" }, { value: "ADMIN", label: "Administrador" }] }] },
} as const
export function Maintenance({ kind, user }: { kind: Kind; user: User }) {
  const [rows, setRows] = useState<Array<Customer | Product | User>>([])
  const [editing, setEditing] = useState<Customer | Product | User | null | undefined>(undefined)
  const d = definitions[kind]
  const load = () => api<Array<Customer | Product | User>>(`/${kind}${kind === "products" ? "?include_inactive=true" : ""}`).then(setRows)
  useEffect(() => { load().catch(() => setRows([])) }, [kind])
  const display = (r: Customer | Product | User) => "full_name" in r ? [r.full_name, r.email, r.role, r.is_active ? "Activo" : "Inactivo"] : "dni" in r ? [`${r.first_names} ${r.last_names}`, r.dni, r.phone, r.status] : [r.name, r.code, r.category, r.is_active ? "Activo" : "Inactivo"]
  const canWrite = kind !== "users" || user.role === "ADMIN"
  return <>
    <div className="page-title"><div><p className="eyebrow">MANTENIMIENTO</p><h1>{d.title}</h1></div>{canWrite && <button onClick={() => setEditing(null)}>Nuevo</button>}</div>
    <section className="panel"><div className="table-wrap"><table><thead><tr><th>Nombre</th><th>Referencia</th><th>Detalle</th><th>Estado / rol</th>{canWrite && <th />}</tr></thead><tbody>{rows.map(r => <tr key={r.id}>{display(r).map((v, i) => <td key={i}>{v}</td>)}{canWrite && <td><button className="link" onClick={() => setEditing(r)}>Editar</button></td>}</tr>)}{!rows.length && <tr><td colSpan={5}>No hay registros disponibles.</td></tr>}</tbody></table></div></section>
    {editing !== undefined && <CrudModal title={editing ? `Editar ${kind.slice(0, -1)}` : `Nuevo ${kind.slice(0, -1)}`} fields={d.fields as never} initial={editing || (kind === "products" ? { is_active: true } : {})} onClose={() => setEditing(undefined)} onSave={async data => { if (editing && kind !== "users") delete data.dni; if (editing && kind === "users") { delete data.email; if (!data.password) delete data.password }; await api(`/${kind}${editing ? `/${editing.id}` : ""}`, { method: editing ? "PATCH" : "POST", body: JSON.stringify(data) }); await load() }} />}
  </>
}
