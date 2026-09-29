import { useEffect, useState } from "react";
import { CrudModal } from "../../components/CrudModal";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import { api } from "../../services/api";
import type {
  Paged,
  Product,
  RecoveryAlert,
  RecoveryCustomer,
  TypificationTree,
  User,
} from "../../services/types";

function options(nodes: TypificationTree[], depth = 0): Array<{ value: string; label: string }> {
  return nodes.flatMap((node) => [
    { value: node.id, label: `${"  ".repeat(depth)}${node.name} (${node.code})` },
    ...options(node.children, depth + 1),
  ]);
}
function overdue(date: string) {
  return Math.max(0, Math.floor((Date.now() - new Date(`${date}T00:00:00`).getTime()) / 86400000));
}
type QueueRow = RecoveryAlert &
  Pick<RecoveryCustomer, "customer_id" | "dni" | "first_names" | "last_names">;

export function RecoveryQueue() {
  const [data, setData] = useState<Paged<RecoveryCustomer>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
    pages: 0,
  });
  const [advisors, setAdvisors] = useState<User[]>([]);
  const [tree, setTree] = useState<TypificationTree[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selected, setSelected] = useState<RecoveryAlert | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState({
    typification_id: "",
    min_days_overdue: "",
    max_days_overdue: "",
    q: "",
    product_id: "",
    status: "",
  });
  const [error, setError] = useState("");
  const load = (page = data.page, active = filters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    return api<Paged<RecoveryCustomer> | RecoveryCustomer[]>(
      `/supervision/recovery-queue?${query}`,
    ).then((value) => {
      setData(asPaged(value, page));
      setSelectedIds(new Set());
    });
  };
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar la cola de recuperación."));
    api<Paged<User> | User[]>("/users?page=1&page_size=200")
      .then((value) =>
        setAdvisors(asPaged(value).items.filter((u) => u.role === "ASESOR" && u.is_active)),
      )
      .catch(() => {});
    api<TypificationTree[]>("/configuration/contact-typifications/tree")
      .then(setTree)
      .catch(() => {});
    api<Paged<Product> | Product[]>("/products?page=1&page_size=200")
      .then((value) => setProducts(asPaged(value).items))
      .catch(() => {});
  }, []);
  const rows: QueueRow[] = data.items.flatMap((customer) =>
    customer.alerts.map((alert) => ({
      ...alert,
      customer_id: customer.customer_id,
      dni: customer.dni,
      first_names: customer.first_names,
      last_names: customer.last_names,
    })),
  );
  const allSelected = rows.length > 0 && rows.every((row) => selectedIds.has(row.id));
  const toggle = (id: string) =>
    setSelectedIds((current) => {
      const next = new Set(current);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">SUPERVISIÓN</p>
          <h1>Cola de recuperación</h1>
          <p>Prioriza alertas vencidas y asígnalas al asesor adecuado.</p>
        </div>
        <div className="header-metric">
          <b>{data.total}</b>
          <span>clientes visibles</span>
        </div>
      </div>
      <section className="panel filters">
        <div className="panel-heading">
          <div>
            <h2>Filtros de priorización</h2>
            <p>La tipificación incluye todas sus subtipificaciones.</p>
          </div>
          <button
            className="secondary"
            onClick={() => {
              const reset = {
                typification_id: "",
                min_days_overdue: "",
                max_days_overdue: "",
                q: "",
                product_id: "",
                status: "",
              };
              setFilters(reset);
              load(1, reset).catch(() => setError("No fue posible actualizar la cola."));
            }}
          >
            Limpiar
          </button>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            load(1).catch((reason) =>
              setError(
                reason instanceof Error ? reason.message : "No fue posible actualizar la cola.",
              ),
            );
          }}
        >
          <div className="filter-grid">
            <label>
              Cliente
              <input
                placeholder="DNI, nombre, teléfono o correo"
                value={filters.q}
                onChange={(event) => setFilters((value) => ({ ...value, q: event.target.value }))}
              />
            </label>
            <label>
              Producto
              <select
                value={filters.product_id}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, product_id: event.target.value }))
                }
              >
                <option value="">Todos los productos</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name} ({product.code})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Estado
              <select
                value={filters.status}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, status: event.target.value }))
                }
              >
                <option value="">Todos los estados</option>
                <option value="VENCIDO_NO_GESTIONADO">Vencida</option>
                <option value="REPROGRAMADO">Reprogramada</option>
                <option value="PENDIENTE">Pendiente</option>
                <option value="SIN_RESPUESTA">Sin respuesta</option>
              </select>
            </label>
            <label>
              Última tipificación
              <select
                value={filters.typification_id}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, typification_id: event.target.value }))
                }
              >
                <option value="">Todas las tipificaciones</option>
                {options(tree).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Días vencidos desde
              <input
                type="number"
                min="0"
                value={filters.min_days_overdue}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, min_days_overdue: event.target.value }))
                }
              />
            </label>
            <label>
              Días vencidos hasta
              <input
                type="number"
                min="0"
                value={filters.max_days_overdue}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, max_days_overdue: event.target.value }))
                }
              />
            </label>
            <button>Aplicar filtros</button>
          </div>
        </form>
        {error && <p className="form-error">{error}</p>}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Alertas en recuperación</h2>
            <p>Selecciona alertas de esta página para reasignarlas en bloque.</p>
          </div>
          <div className="row-actions">
            <button
              className="secondary"
              disabled={!rows.length}
              onClick={() =>
                setSelectedIds(allSelected ? new Set() : new Set(rows.map((row) => row.id)))
              }
            >
              {allSelected ? "Limpiar página" : "Seleccionar página"}
            </button>
            <button disabled={!selectedIds.size} onClick={() => setBulkOpen(true)}>
              Asignar {selectedIds.size} seleccionadas
            </button>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>
                  <input
                    aria-label="Seleccionar página"
                    type="checkbox"
                    checked={allSelected}
                    onChange={() =>
                      setSelectedIds(allSelected ? new Set() : new Set(rows.map((row) => row.id)))
                    }
                  />
                </th>
                <th>Cliente</th>
                <th>Producto</th>
                <th>Vencido</th>
                <th>Tipificación</th>
                <th>Asesor</th>
                <th>Acción</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <input
                      aria-label={`Seleccionar ${row.product_name}`}
                      type="checkbox"
                      checked={selectedIds.has(row.id)}
                      onChange={() => toggle(row.id)}
                    />
                  </td>
                  <td>
                    <b>
                      {row.first_names} {row.last_names}
                    </b>
                    <small className="table-detail">DNI {row.dni}</small>
                  </td>
                  <td>
                    <b>{row.product_name}</b>
                    <small className="table-detail">
                      {row.product_code} · Venta {row.sale_date}
                    </small>
                  </td>
                  <td className={overdue(row.alert_date) > 0 ? "danger-text" : ""}>
                    {overdue(row.alert_date)} días
                  </td>
                  <td>{row.latest_contact_typification || "Sin gestión"}</td>
                  <td>{row.assigned_advisor_name || "Sin asignar"}</td>
                  <td>
                    <button className="secondary" onClick={() => setSelected(row)}>
                      Reasignar
                    </button>
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={7}>No hay alertas que coincidan con los filtros seleccionados.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          data={data}
          onPageChange={(page) =>
            load(page).catch(() => setError("No fue posible cargar la página."))
          }
        />
      </section>
      {selected && (
        <CrudModal
          title={`Reasignar: ${selected.product_name}`}
          onClose={() => setSelected(null)}
          fields={[
            {
              name: "assigned_advisor_id",
              label: "Asesor responsable",
              required: true,
              options: [
                { value: "", label: "Selecciona un asesor" },
                ...advisors.map((advisor) => ({ value: advisor.id, label: advisor.full_name })),
              ],
            },
            { name: "reason", label: "Motivo de la reasignación", required: true },
          ]}
          onSave={async (form) => {
            await api(`/supervision/alerts/${selected.id}/assign`, {
              method: "POST",
              body: JSON.stringify(form),
            });
            await load();
          }}
        />
      )}
      {bulkOpen && (
        <CrudModal
          title={`Asignar ${selectedIds.size} alertas`}
          onClose={() => setBulkOpen(false)}
          fields={[
            {
              name: "assigned_advisor_id",
              label: "Asesor responsable",
              required: true,
              options: [
                { value: "", label: "Selecciona un asesor" },
                ...advisors.map((advisor) => ({ value: advisor.id, label: advisor.full_name })),
              ],
            },
            { name: "reason", label: "Motivo de la reasignación", required: true },
          ]}
          onSave={async (form) => {
            await api("/supervision/alerts/bulk-assign", {
              method: "POST",
              body: JSON.stringify({ ...form, alert_ids: [...selectedIds] }),
            });
            setBulkOpen(false);
            await load();
          }}
        />
      )}
    </>
  );
}
