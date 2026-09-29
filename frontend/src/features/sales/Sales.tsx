import { useEffect, useState } from "react";
import { CrudModal } from "../../components/CrudModal";
import { ConfirmModal, Modal } from "../../components/Modal";
import { api } from "../../services/api";
import { StatCard } from "../../components/StatCard";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import type {
  AdvisorSalesMetrics,
  Customer,
  Paged,
  Product,
  Sale,
  User,
} from "../../services/types";

type SaleLine = { product_id: string; quantity: number };

const customerFields = [
  { name: "dni", label: "DNI", required: true },
  { name: "first_names", label: "Nombres", required: true },
  { name: "last_names", label: "Apellidos", required: true },
  { name: "phone", label: "Teléfono", required: true },
  { name: "email", label: "Correo", type: "email" },
  { name: "condition", label: "Enfermedad o condición" },
  { name: "birth_year", label: "Año de nacimiento", type: "number" },
  { name: "sales_district", label: "Distrito de venta" },
];

export function Sales({ user }: { user: User }) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [salesPage, setSalesPage] = useState<Paged<Sale>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
    pages: 0,
  });
  const [metrics, setMetrics] = useState<AdvisorSalesMetrics | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Sale | null>(null);
  const [removing, setRemoving] = useState<Sale | null>(null);
  const [customerModal, setCustomerModal] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [lines, setLines] = useState<SaleLine[]>([{ product_id: "", quantity: 1 }]);
  const [channel, setChannel] = useState("TV");
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ q: "", product_id: "", status: "" });
  const advisor = user.role === "ASESOR";
  const load = async (page = salesPage.page, active = filters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    const [customerRows, productRows, saleRows, advisorMetrics] = await Promise.all([
      api<Paged<Customer> | Customer[]>("/customers?page=1&page_size=200"),
      api<Paged<Product> | Product[]>("/products?page=1&page_size=200"),
      api<Paged<Sale> | Sale[]>(`/sales?${query}`),
      advisor ? api<AdvisorSalesMetrics>(`/sales/me/metrics?${query}`) : Promise.resolve(null),
    ]);
    setCustomers(asPaged(customerRows).items);
    setProducts(asPaged(productRows).items.filter((product) => product.is_active));
    setSalesPage(asPaged(saleRows, page));
    setMetrics(advisorMetrics);
  };
  const sales = salesPage.items;
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar el espacio de ventas."));
  }, []);
  const closeSale = () => {
    setOpen(false);
    setEditing(null);
    setError("");
  };
  const saveCustomer = async (data: Record<string, unknown>) => {
    const customer = await api<Customer>("/customers", {
      method: "POST",
      body: JSON.stringify(data),
    });
    setCustomers((rows) =>
      [...rows, customer].sort((a, b) =>
        `${a.last_names} ${a.first_names}`.localeCompare(`${b.last_names} ${b.first_names}`),
      ),
    );
    setCustomerId(customer.id);
    setError("");
  };
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      const payload = {
        customer_id: customerId,
        sale_date: form.get("sale_date"),
        notes: form.get("notes") || null,
        acquisition_channel: channel,
        acquisition_channel_detail:
          channel === "OTROS" ? form.get("acquisition_channel_detail") : null,
        items: lines,
      };
      await api(editing ? `/sales/${editing.id}` : "/sales", {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });
      closeSale();
      setLines([{ product_id: "", quantity: 1 }]);
      load().catch(() =>
        setError("La venta se registró, pero no fue posible actualizar el historial."),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible guardar la venta.");
    }
  };
  const customerName = (sale: Sale) => {
    if (sale.customer_first_names || sale.customer_last_names)
      return `${sale.customer_last_names || ""} ${sale.customer_first_names || ""}`.trim();
    const customerId = sale.customer_id;
    const customer = customers.find((row) => row.id === customerId);
    return customer ? `${customer.last_names} ${customer.first_names}` : customerId;
  };
  const saleProducts = (sale: Sale) =>
    sale.items
      .map((item) => {
        const product = products.find((row) => row.id === item.product_id);
        const detail = [item.product_brand, item.product_category].filter(Boolean).join(" / ");
        return `${item.product_name || product?.name || item.product_id}${detail ? ` (${detail})` : ""} x${item.quantity}`;
      })
      .join(", ");
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">VENTAS</p>
          <h1>Ventas</h1>
          <p>
            {advisor
              ? "Registra y consulta tus ventas."
              : "Consulta las ventas registradas por el equipo."}
          </p>
        </div>
        <button
          onClick={() => {
            setError("");
            setCustomerId("");
            setLines([{ product_id: "", quantity: 1 }]);
            setChannel("TV");
            setOpen(true);
          }}
        >
          Registrar venta
        </button>
      </div>
      {advisor && (
        <section className="stats">
          <StatCard label="Ventas confirmadas" value={metrics?.confirmed_sales ?? "-"} />
          <StatCard
            label="Productos confirmados"
            value={metrics?.confirmed_items ?? "-"}
            accent="green"
          />
          <StatCard label="Recompras" value={metrics?.repurchase_sales ?? "-"} accent="purple" />
          <StatCard
            label="Productos en recompra"
            value={metrics?.repurchase_items ?? "-"}
            accent="orange"
          />
        </section>
      )}
      <section className="panel filters">
        <div className="panel-heading">
          <div>
            <h2>Filtros</h2>
            <p>Busca ventas por cliente, producto o estado.</p>
          </div>
          <button
            className="secondary"
            onClick={() => {
              const reset = { q: "", product_id: "", status: "" };
              setFilters(reset);
              load(1, reset).catch(() => setError("No fue posible actualizar las ventas."));
            }}
          >
            Limpiar
          </button>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            load(1).catch(() => setError("No fue posible actualizar las ventas."));
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
                <option value="CONFIRMADA">Confirmada</option>
                <option value="PENDIENTE_REVISION_DUPLICADO">Pendiente de revisión</option>
                <option value="ANULADA">Anulada</option>
                <option value="RECHAZADA_DUPLICADO">Rechazada</option>
              </select>
            </label>
            <button>Aplicar filtros</button>
          </div>
        </form>
      </section>
      <section className="panel sales-history">
        <div className="panel-heading">
          <div>
            <h2>{advisor ? "Mi historial de ventas" : "Historial de ventas"}</h2>
            <p>
              {advisor
                ? "Solo se muestran las ventas que registraste."
                : "Incluye las ventas registradas por todos los asesores."}
            </p>
          </div>
          <span className="header-metric">
            <b>{salesPage.total}</b> registros
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                {!advisor && <th>Vendedor / asesor</th>}
                <th>Cliente</th>
                <th>Productos</th>
                <th>Estado</th>
                {!advisor && <th aria-label="Acciones" />}
              </tr>
            </thead>
            <tbody>
              {sales.map((sale) => (
                <tr key={sale.id}>
                  <td>{sale.sale_date}</td>
                  {!advisor && <td>{sale.advisor_full_name || sale.advisor_id}</td>}
                  <td>
                    {customerName(sale)}
                    {(sale.customer_dni || sale.customer_phone) && (
                      <small className="table-detail">
                        {[sale.customer_dni && `DNI ${sale.customer_dni}`, sale.customer_phone]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                    )}
                  </td>
                  <td>{saleProducts(sale)}</td>
                  <td>
                    <span
                      className={`status ${sale.status === "CONFIRMADA" ? "success" : "neutral"}`}
                    >
                      {sale.status.replaceAll("_", " ")}
                    </span>
                  </td>
                  {!advisor && (
                    <td>
                      <div className="row-actions">
                        <button
                          className="link"
                          onClick={() => {
                            setError("");
                            setCustomerId(sale.customer_id);
                            setLines(
                              sale.items.map((item) => ({
                                product_id: item.product_id,
                                quantity: item.quantity,
                              })),
                            );
                            setChannel(sale.acquisition_channel || "TV");
                            setEditing(sale);
                            setOpen(true);
                          }}
                        >
                          Editar
                        </button>
                        <button className="link danger-link" onClick={() => setRemoving(sale)}>
                          Eliminar
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
              {!sales.length && (
                <tr>
                  <td colSpan={advisor ? 4 : 6}>No hay ventas registradas.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          data={salesPage}
          onPageChange={(page) =>
            load(page).catch(() => setError("No fue posible cargar la página."))
          }
        />
      </section>
      {open && (
        <Modal title={editing ? "Editar venta" : "Registrar venta"} onClose={closeSale}>
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>
                Cliente
                <select
                  value={customerId}
                  onChange={(event) =>
                    event.target.value === "__create__"
                      ? setCustomerModal(true)
                      : setCustomerId(event.target.value)
                  }
                  required
                >
                  <option value="">Selecciona un cliente</option>
                  <option value="__create__">Crear cliente</option>
                  {customers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.last_names} {customer.first_names} - {customer.dni}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Fecha de venta
                <input
                  name="sale_date"
                  type="date"
                  defaultValue={editing?.sale_date || new Date().toISOString().slice(0, 10)}
                  required
                />
              </label>
              <label>
                Canal de primera venta
                <select value={channel} onChange={(event) => setChannel(event.target.value)}>
                  <option value="TV">TV</option>
                  <option value="DIGITAL">Digital</option>
                  <option value="OTROS">Otros</option>
                </select>
              </label>
              {channel === "OTROS" && (
                <label>
                  Detalle del canal
                  <input
                    name="acquisition_channel_detail"
                    defaultValue={editing?.acquisition_channel_detail || ""}
                    required
                  />
                </label>
              )}
            </div>
            <div className="sale-lines">
              <h3>Productos</h3>
              {lines.map((line, index) => (
                <div className="sale-line" key={index}>
                  <select
                    value={line.product_id}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, product_id: event.target.value } : item,
                        ),
                      )
                    }
                    required
                  >
                    <option value="">Selecciona un producto</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.code})
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label="Cantidad"
                    type="number"
                    min="1"
                    value={line.quantity}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, quantity: Number(event.target.value) }
                            : item,
                        ),
                      )
                    }
                    required
                  />
                  {lines.length > 1 && (
                    <button
                      className="secondary"
                      type="button"
                      onClick={() =>
                        setLines((current) => current.filter((_, itemIndex) => itemIndex !== index))
                      }
                    >
                      Quitar
                    </button>
                  )}
                </div>
              ))}
              <button
                className="secondary"
                type="button"
                onClick={() => setLines((current) => [...current, { product_id: "", quantity: 1 }])}
              >
                Agregar producto
              </button>
            </div>
            <label className="notes">
              Notas opcionales
              <textarea name="notes" defaultValue={editing?.notes || ""} maxLength={4000} />
            </label>
            {error && <p className="form-error">{error}</p>}
            <footer>
              <button type="button" className="secondary" onClick={closeSale}>
                Cancelar
              </button>
              <button>Guardar venta</button>
            </footer>
          </form>
        </Modal>
      )}
      {customerModal && (
        <CrudModal
          title="Crear cliente"
          fields={customerFields}
          onClose={() => setCustomerModal(false)}
          onSave={saveCustomer}
        />
      )}
      {removing && (
        <ConfirmModal
          title="Eliminar venta permanentemente"
          message={`Eliminarás de forma permanente la venta de ${customerName(removing)} del ${removing.sale_date}, sus productos y alertas relacionadas. Esta acción no se puede deshacer.`}
          onClose={() => setRemoving(null)}
          onConfirm={async () => {
            await api(`/sales/${removing.id}`, { method: "DELETE" });
            await load();
          }}
        />
      )}
    </>
  );
}
