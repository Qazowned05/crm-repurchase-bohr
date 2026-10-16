import { useEffect, useState } from "react";
import { CustomerModal } from "../../components/CustomerModal";
import { ConfirmModal, Modal } from "../../components/Modal";
import { SearchSelect } from "../../components/SearchSelect";
import { api, listAll } from "../../services/api";
import { StatCard } from "../../components/StatCard";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import { DataPanel } from "../../components/DataPanel";
import { PageHeader } from "../../components/PageHeader";
import type {
  AdvisorSalesMetrics,
  Customer,
  Paged,
  Product,
  Sale,
  User,
} from "../../services/types";

type SaleLine = { product_id: string; quantity: number };

function formatDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { dateStyle: "medium" }).format(
    new Date(`${value}T00:00:00`),
  );
}

function formatCurrency(value?: string | null) {
  if (value == null) return "No registrado";
  return new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(
    Number(value),
  );
}

function saleStatusClass(status: string) {
  if (status === "CONFIRMADA") return "status success";
  if (status === "PENDIENTE_REVISION_DUPLICADO") return "status warning";
  return "status neutral";
}

function SaleDetails({ sale, onClose }: { sale: Sale; onClose: () => void }) {
  const customerName =
    `${sale.customer_last_names || ""} ${sale.customer_first_names || ""}`.trim();
  const customerContact = [
    sale.customer_dni && `DNI ${sale.customer_dni}`,
    sale.customer_phone,
    sale.customer_email,
  ]
    .filter(Boolean)
    .join(" · ");
  const channel = [sale.acquisition_channel, sale.acquisition_channel_detail]
    .filter(Boolean)
    .join(" · ");
  const total = sale.items.every((item) => item.unit_price != null)
    ? sale.items.reduce((sum, item) => sum + Number(item.unit_price) * item.quantity, 0)
    : null;
  return (
    <Modal title="Detalle de venta" onClose={onClose}>
      <div className="alert-summary sale-summary alert-context">
        <div>
          <span>Cliente</span>
          <b>{customerName || "Sin cliente"}</b>
          <small>{customerContact}</small>
        </div>
        <div>
          <span>Fecha de venta</span>
          <b>{formatDate(sale.sale_date)}</b>
          <small>{channel || "Canal no registrado"}</small>
        </div>
        <div>
          <span>Registrada por</span>
          <b>{sale.advisor_full_name || "Usuario no disponible"}</b>
          <small>{sale.advisor_email || ""}</small>
        </div>
        <div>
          <span>Estado</span>
          <b className={sale.status === "CONFIRMADA" ? "success-text" : "pending-text"}>
            {sale.status.replaceAll("_", " ")}
          </b>
        </div>
        <div>
          <span>Total de venta</span>
          <b>{total == null ? "No registrado" : formatCurrency(String(total))}</b>
        </div>
      </div>
      <section className="sale-detail-section">
        <h3>Productos</h3>
        <div className="table-wrap">
          <table className="sale-detail-items">
            <thead>
              <tr>
                <th>Producto</th>
                <th>Cantidad</th>
                <th>Precio unitario</th>
                <th>Tipo</th>
              </tr>
            </thead>
            <tbody>
              {sale.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <b>{item.product_name || "Producto no disponible"}</b>
                    <span className="table-detail">
                      {[item.product_code, item.product_brand, item.product_category]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </td>
                  <td>{item.quantity}</td>
                  <td>{formatCurrency(item.unit_price)}</td>
                  <td>{item.purchase_type?.replaceAll("_", " ") || "Sin clasificar"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="sale-detail-section">
        <h3>Notas</h3>
        <p>{sale.notes || "Sin notas registradas."}</p>
      </section>
    </Modal>
  );
}

export function Sales({ user }: { user: User }) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [advisors, setAdvisors] = useState<User[]>([]);
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
  const [selectedSale, setSelectedSale] = useState<Sale | null>(null);
  const [customerModal, setCustomerModal] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [advisorId, setAdvisorId] = useState("");
  const [lines, setLines] = useState<SaleLine[]>([{ product_id: "", quantity: 1 }]);
  const [channel, setChannel] = useState("TV");
  const [error, setError] = useState("");
  const [saleDirty, setSaleDirty] = useState(false);
  const [filters, setFilters] = useState({ q: "", product_id: "", status: "", advisor_id: "" });
  const advisor = user.role === "ASESOR";
  const load = async (page = salesPage.page, active = filters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    const [customerRows, productRows, saleRows, advisorMetrics, advisorRows] = await Promise.all([
      api<Customer[]>("/customers/sale-options"),
      listAll<Product>("/products"),
      api<Paged<Sale> | Sale[]>(`/sales?${query}`),
      advisor ? api<AdvisorSalesMetrics>("/sales/me/metrics") : Promise.resolve(null),
      advisor ? Promise.resolve([]) : api<User[]>("/users/advisors"),
    ]);
    setCustomers(customerRows);
    setProducts(productRows.filter((product) => product.is_active));
    setSalesPage(asPaged(saleRows, page));
    setMetrics(advisorMetrics);
    setAdvisors(advisorRows);
  };
  const sales = salesPage.items;
  const selectedCustomer = customers.find((customer) => customer.id === customerId);
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar el espacio de ventas."));
  }, []);
  const closeSale = () => {
    setOpen(false);
    setEditing(null);
    setError("");
    setSaleDirty(false);
  };
  const requestCloseSale = () => {
    if (!saleDirty || window.confirm("Hay cambios sin guardar. ¿Deseas descartarlos?")) closeSale();
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
        advisor_id: !advisor && !editing && advisorId ? advisorId : undefined,
        sale_date: form.get("sale_date"),
        notes: form.get("notes") || null,
        acquisition_channel: channel,
        acquisition_channel_detail:
          channel === "OTROS" ? form.get("acquisition_channel_detail") : null,
        customer_condition: String(form.get("customer_condition") || "") || undefined,
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
  const saleProductSummary = (sale: Sale) => {
    const [first, ...remaining] = sale.items;
    if (!first) return { primary: "Sin productos", secondary: "" };
    const product = products.find((row) => row.id === first.product_id);
    return {
      primary: `${first.product_name || product?.name || "Producto"} x${first.quantity}`,
      secondary: remaining.length
        ? `+ ${remaining.length} ${remaining.length === 1 ? "producto" : "productos"}`
        : first.product_code || "",
    };
  };
  return (
    <>
      <PageHeader
        eyebrow="VENTAS"
        title="Ventas"
        description={
          advisor
            ? "Registra ventas y consulta el historial de tu cartera."
            : "Consulta las ventas registradas por el equipo."
        }
        actions={
          <button
            onClick={() => {
              setError("");
              setCustomerId("");
              setAdvisorId("");
              setLines([{ product_id: "", quantity: 1 }]);
              setChannel("TV");
              setOpen(true);
            }}
          >
            Registrar venta
          </button>
        }
      />
      {advisor && (
        <section className="stats">
          <StatCard
            label="Ventas confirmadas"
            value={metrics?.confirmed_sales ?? "-"}
            icon="check"
          />
          <StatCard
            label="Productos confirmados"
            value={metrics?.confirmed_items ?? "-"}
            accent="green"
            icon="package"
          />
          <StatCard
            label="Recompras"
            value={metrics?.repurchase_sales ?? "-"}
            accent="purple"
            icon="refresh"
          />
          <StatCard
            label="Productos en recompra"
            value={metrics?.repurchase_items ?? "-"}
            accent="orange"
            icon="package"
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
              const reset = { q: "", product_id: "", status: "", advisor_id: "" };
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
            {!advisor && (
              <label>
                Asesor que registró
                <select
                  value={filters.advisor_id}
                  onChange={(event) =>
                    setFilters((value) => ({ ...value, advisor_id: event.target.value }))
                  }
                >
                  <option value="">Todos los asesores</option>
                  {advisors.map((advisor) => (
                    <option key={advisor.id} value={advisor.id}>
                      {advisor.full_name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button>Aplicar filtros</button>
          </div>
        </form>
      </section>
      <DataPanel
        className="sales-history sales-register-panel"
        title={advisor ? "Ventas de mi cartera" : "Historial de ventas"}
        description={
          advisor
            ? "Incluye ventas de tus clientes, incluso si otro asesor las registró."
            : "Incluye las ventas registradas por todos los asesores."
        }
        metric={
          <span className="header-metric">
            <b>{salesPage.total}</b> registros
          </span>
        }
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Fecha</th>
                <th>Productos</th>
                <th>Registrada por</th>
                <th>Estado</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {sales.map((sale) => (
                <tr key={sale.id}>
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
                  <td>{formatDate(sale.sale_date)}</td>
                  <td>
                    {(() => {
                      const summary = saleProductSummary(sale);
                      return (
                        <>
                          <b>{summary.primary}</b>
                          {summary.secondary && (
                            <span className="table-detail">{summary.secondary}</span>
                          )}
                        </>
                      );
                    })()}
                  </td>
                  <td>{sale.advisor_full_name || sale.advisor_id}</td>
                  <td>
                    <span className={saleStatusClass(sale.status)}>
                      {sale.status.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button className="secondary" onClick={() => setSelectedSale(sale)}>
                        Ver
                      </button>
                      {!advisor && (
                        <>
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
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {!sales.length && (
                <tr>
                  <td colSpan={6}>No hay ventas registradas.</td>
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
      </DataPanel>
      {open && (
        <Modal title={editing ? "Editar venta" : "Registrar venta"} onClose={requestCloseSale}>
          <form className="sale-form" onSubmit={submit} onChange={() => setSaleDirty(true)}>
            <div className="form-grid sale-details-grid">
              <label>
                Cliente
                <SearchSelect
                  value={customerId}
                  onChange={setCustomerId}
                  placeholder="Busca por nombre o DNI"
                  required
                  actionLabel="Crear cliente"
                  onAction={() => setCustomerModal(true)}
                  options={customers.map((customer) => ({
                    value: customer.id,
                    label: `${customer.last_names} ${customer.first_names} - ${customer.dni}`,
                  }))}
                />
                <small>La venta no cambia el asesor responsable de la cartera.</small>
              </label>
              {!advisor && !editing && (
                <label>
                  Registrar a nombre de
                  <SearchSelect
                    value={advisorId}
                    onChange={setAdvisorId}
                    placeholder="Supervisor que registra"
                    options={advisors.map((advisor) => ({
                      value: advisor.id,
                      label: advisor.full_name,
                    }))}
                  />
                  <small>
                    Solo atribuye esta venta; no cambia la cartera ni las alertas del cliente.
                  </small>
                </label>
              )}
              {selectedCustomer && (
                <label className="notes" key={selectedCustomer.id}>
                  Enfermedad o condición
                  <textarea
                    name="customer_condition"
                    defaultValue={selectedCustomer.condition || ""}
                    maxLength={500}
                    placeholder="Sin información"
                  />
                </label>
              )}
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
                  <SearchSelect
                    value={line.product_id}
                    placeholder="Busca por código o nombre"
                    required
                    onChange={(product_id) =>
                      setLines((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, product_id } : item,
                        ),
                      )
                    }
                    options={products.map((product) => ({
                      value: product.id,
                      label: `${product.name} (${product.code})`,
                    }))}
                  />
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
                className="secondary sale-add-product"
                type="button"
                onClick={() => setLines((current) => [...current, { product_id: "", quantity: 1 }])}
              >
                Agregar producto
              </button>
            </div>
            <label className="notes sale-notes">
              Notas opcionales
              <textarea name="notes" defaultValue={editing?.notes || ""} maxLength={4000} />
            </label>
            {error && <p className="form-error">{error}</p>}
            <footer>
              <button type="button" className="secondary" onClick={requestCloseSale}>
                Cancelar
              </button>
              <button>Guardar venta</button>
            </footer>
          </form>
        </Modal>
      )}
      {customerModal && (
        <CustomerModal
          title="Crear cliente"
          role={user.role}
          onClose={() => setCustomerModal(false)}
          onSave={saveCustomer}
        />
      )}
      {selectedSale && <SaleDetails sale={selectedSale} onClose={() => setSelectedSale(null)} />}
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
