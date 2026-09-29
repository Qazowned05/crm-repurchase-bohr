import { useEffect, useState } from "react";
import { Modal } from "../../components/Modal";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import { api } from "../../services/api";
import type { ContactAttempt, ManagedAlert, Paged, Product } from "../../services/types";

const closedStatuses = new Set([
  "RECOMPRA_LOGRADA",
  "COMPRA_OTRO_PRODUCTO",
  "CERRADO_POR_TIPIFICACION",
  "CANCELADO_POR_RECOMPRA",
  "CANCELADO_POR_ANULACION",
  "NO_INTERESADO",
  "VENCIDO_NO_GESTIONADO",
]);

function formatDate(value?: string | null, withTime = false) {
  if (!value) return "Sin registro";
  const date = new Date(withTime ? value : `${value}T00:00:00`);
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" } : {}),
  }).format(date);
}

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

function alertStatusClass(status: string) {
  return `status alert-status-${status.toLowerCase().replaceAll("_", "-")}`;
}

function latestAttempt(alert: ManagedAlert): ContactAttempt | undefined {
  return alert.contact_attempts[alert.contact_attempts.length - 1];
}

function groupByCustomer(alerts: ManagedAlert[]): ManagedAlert[][] {
  const groups = new Map<string, ManagedAlert[]>();
  alerts.forEach((alert) => {
    const customerKey = alert.customer_id || alert.customer_dni || alert.id;
    groups.set(customerKey, [...(groups.get(customerKey) || []), alert]);
  });
  return Array.from(groups.values());
}

function AlertDetails({ alert, onClose }: { alert: ManagedAlert; onClose: () => void }) {
  const closed = closedStatuses.has(alert.status);
  return (
    <Modal title="Detalle de gestión" onClose={onClose}>
      <div className="alert-summary">
        <div>
          <span>Cliente</span>
          <b>
            {`${alert.customer_first_names || ""} ${alert.customer_last_names || ""}`.trim() ||
              "Sin cliente"}
          </b>
          <small>{alert.customer_dni ? `DNI ${alert.customer_dni}` : ""}</small>
        </div>
        <div>
          <span>Producto</span>
          <b>{alert.product_name || "Sin producto"}</b>
          <small>{alert.product_code || ""}</small>
        </div>
        <div>
          <span>Estado</span>
          <b className={closed ? "closed-text" : "pending-text"}>
            {closed ? "Cerrada" : statusLabel(alert.status)}
          </b>
          <small>{statusLabel(alert.status)}</small>
        </div>
        <div>
          <span>Asesor responsable</span>
          <b>{alert.assigned_advisor_name || "Sin asignar"}</b>
          <small>{alert.assigned_advisor_email || ""}</small>
        </div>
      </div>
      {closed && (
        <p className="closure-reason">
          <b>Motivo de cierre:</b> {alert.closure_reason || "No registrado"}
        </p>
      )}
      {!closed && (
        <p className="follow-up-note">
          <b>Próxima acción:</b> {formatDate(alert.next_action_date)}
        </p>
      )}
      <p className="follow-up-note">
        <b>Tipo de alerta:</b> {alert.alert_type?.replaceAll("_", " ") || "AUTOMÁTICA"}
        {alert.assignment_reason ? ` · Motivo de asignación: ${alert.assignment_reason}` : ""}
      </p>
      <h3 className="history-title">Historial de gestión</h3>
      {alert.contact_attempts.length ? (
        <ol className="management-history">
          {alert.contact_attempts.map((attempt) => (
            <li key={attempt.id}>
              <div>
                <b>{formatDate(attempt.contacted_at, true)}</b>
                <span>{attempt.user_name || "Usuario no disponible"}</span>
              </div>
              <p>
                <b>Tipificación:</b>{" "}
                {[attempt.parent_typification_name, attempt.child_typification_name]
                  .filter(Boolean)
                  .join(" / ") || attempt.result}
              </p>
              <p>
                <b>Observación:</b> {attempt.observation || attempt.note || "Sin observación"}
              </p>
              <p>
                <b>Siguiente acción:</b> {formatDate(attempt.next_action_date)}
              </p>
            </li>
          ))}
        </ol>
      ) : (
        <p className="empty-state">Esta alerta aún no tiene gestiones registradas.</p>
      )}
    </Modal>
  );
}

export function AlertRegister() {
  const [data, setData] = useState<Paged<ManagedAlert>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
    pages: 0,
  });
  const [selected, setSelected] = useState<ManagedAlert | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [filters, setFilters] = useState({
    date_from: "",
    date_to: "",
    state: "",
    q: "",
    product_id: "",
    status: "",
    alert_type: "",
  });
  const [error, setError] = useState("");
  const load = (page = data.page, active = filters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    return api<Paged<ManagedAlert> | ManagedAlert[]>(`/alerts/register?${query}`).then((value) =>
      setData(asPaged(value, page)),
    );
  };
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar el registro de alertas."));
    api<Paged<Product> | Product[]>("/products?page=1&page_size=200")
      .then((value) => setProducts(asPaged(value).items))
      .catch(() => {});
  }, []);
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">GESTIÓN</p>
          <h1>Registro de alertas</h1>
          <p>Consulta alertas en seguimiento y alertas cerradas con su trazabilidad completa.</p>
        </div>
        <div className="header-metric">
          <b>{data.total}</b>
          <span>alertas visibles</span>
        </div>
      </div>
      <section className="panel filters">
        <div className="panel-heading">
          <div>
            <h2>Filtros</h2>
            <p>El periodo se aplica sobre la fecha de generación de la alerta.</p>
          </div>
          <button
            className="secondary"
            onClick={() => {
              const reset = {
                date_from: "",
                date_to: "",
                state: "",
                q: "",
                product_id: "",
                status: "",
                alert_type: "",
              };
              setFilters(reset);
              setError("");
              load(1, reset).catch((reason) =>
                setError(
                  reason instanceof Error
                    ? reason.message
                    : "No fue posible actualizar el registro.",
                ),
              );
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
                reason instanceof Error ? reason.message : "No fue posible actualizar el registro.",
              ),
            );
          }}
        >
          <div className="register-filter-grid">
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
              Desde
              <input
                type="date"
                value={filters.date_from}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, date_from: event.target.value }))
                }
              />
            </label>
            <label>
              Hasta
              <input
                type="date"
                value={filters.date_to}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, date_to: event.target.value }))
                }
              />
            </label>
            <label>
              Estado
              <select
                value={filters.state}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, state: event.target.value }))
                }
              >
                <option value="">Todos los estados</option>
                <option value="open-follow-up">Seguimiento pendiente</option>
                <option value="closed">Cerradas</option>
              </select>
            </label>
            <label>
              Estado de alerta
              <select
                value={filters.status}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, status: event.target.value }))
                }
              >
                <option value="">Todos</option>
                <option value="PENDIENTE">Pendiente</option>
                <option value="REASIGNADO">Reasignada</option>
                <option value="REPROGRAMADO">Reprogramada</option>
                <option value="SIN_RESPUESTA">Sin respuesta</option>
                <option value="VENCIDO_NO_GESTIONADO">Vencida</option>
                <option value="COMPRA_OTRO_PRODUCTO">Compra de otro producto</option>
              </select>
            </label>
            <label>
              Tipo de alerta
              <select
                value={filters.alert_type}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, alert_type: event.target.value }))
                }
              >
                <option value="">Todos los tipos</option>
                <option value="AUTOMATICA">Automática</option>
                <option value="REASIGNADA">Reasignada</option>
                <option value="SEGUIMIENTO">Seguimiento</option>
              </select>
            </label>
            <button>Aplicar filtros</button>
          </div>
        </form>
        {error && <p className="form-error">{error}</p>}
      </section>
      <section className="panel register-panel">
        <div className="table-wrap">
          <table className="alert-register-table">
            <thead>
              <tr>
                <th>Cliente</th>
                <th>Producto</th>
                <th>Asesor</th>
                <th>Vencimiento</th>
                <th>Estado</th>
                <th>Última gestión</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            {groupByCustomer(data.items).map((customerAlerts) => {
              const customer = customerAlerts[0];
              return (
                <tbody className="alert-register-customer" key={customer.customer_id || customer.id}>
                  {customerAlerts.map((alert, index) => {
                    const latest = latestAttempt(alert);
                    const closed = closedStatuses.has(alert.status);
                    return (
                      <tr key={alert.id}>
                        {index === 0 && (
                          <td rowSpan={customerAlerts.length} className="customer-cell">
                            <b>
                              {`${customer.customer_first_names || ""} ${customer.customer_last_names || ""}`.trim() ||
                                "Sin cliente"}
                            </b>
                            <span className="table-detail">
                              {customer.customer_dni ? `DNI ${customer.customer_dni}` : ""}
                            </span>
                            <span className="table-detail">
                              {customerAlerts.length} {customerAlerts.length === 1 ? "alerta" : "alertas"}
                            </span>
                          </td>
                        )}
                    <td>
                      <b>{alert.product_name || "Sin producto"}</b>
                      <span className="table-detail">{alert.product_code || ""}</span>
                    </td>
                    <td>{alert.assigned_advisor_name || "Sin asignar"}</td>
                    <td>
                      {formatDate(alert.expected_repurchase_date)}
                      <span className="table-detail">Alerta: {formatDate(alert.alert_date)}</span>
                    </td>
                    <td>
                      <span className={alertStatusClass(alert.status)}>{statusLabel(alert.status)}</span>
                      <span className="table-detail">
                        {closed
                          ? alert.closure_reason || statusLabel(alert.status)
                          : `Próxima: ${formatDate(alert.next_action_date)}`}
                      </span>
                    </td>
                    <td>
                      {latest ? (
                        <>
                          <b>
                            {latest.child_typification_name ||
                              latest.parent_typification_name ||
                              latest.result}
                          </b>
                          <span className="table-detail">
                            {formatDate(latest.contacted_at, true)}
                          </span>
                        </>
                      ) : (
                        "Sin gestión"
                      )}
                    </td>
                    <td>
                      <button className="secondary" onClick={() => setSelected(alert)}>
                        Ver detalle
                      </button>
                    </td>
                      </tr>
                    );
                  })}
                </tbody>
              );
            })}
          </table>
        </div>
        {!data.items.length && !error && (
          <div className="empty-state">
            No hay alertas que coincidan con los filtros seleccionados.
          </div>
        )}
        <Pagination
          data={data}
          onPageChange={(page) =>
            load(page).catch(() => setError("No fue posible cargar la página."))
          }
        />
      </section>
      {selected && <AlertDetails alert={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
