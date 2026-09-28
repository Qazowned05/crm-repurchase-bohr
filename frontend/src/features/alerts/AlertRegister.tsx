import { useEffect, useState } from "react";
import { Modal } from "../../components/Modal";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import { api } from "../../services/api";
import type { ContactAttempt, ManagedAlert, Paged } from "../../services/types";

const closedStatuses = new Set([
  "RECOMPRA_LOGRADA",
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

function latestAttempt(alert: ManagedAlert): ContactAttempt | undefined {
  return alert.contact_attempts[alert.contact_attempts.length - 1];
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
            {closed ? "Cerrada" : "Seguimiento pendiente"}
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
  const [data, setData] = useState<Paged<ManagedAlert>>({ items: [], page: 1, page_size: PAGE_SIZE, total: 0, pages: 0 });
  const [selected, setSelected] = useState<ManagedAlert | null>(null);
  const [filters, setFilters] = useState({ date_from: "", date_to: "", state: "" });
  const [error, setError] = useState("");
  const load = (page = data.page, active = filters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    return api<Paged<ManagedAlert> | ManagedAlert[]>(`/alerts/register?${query}`).then((value) => setData(asPaged(value, page)));
  };
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar el registro de alertas."));
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
              const reset = { date_from: "", date_to: "", state: "" };
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
            <tbody>
               {data.items.map((alert) => {
                const latest = latestAttempt(alert);
                const closed = closedStatuses.has(alert.status);
                return (
                  <tr key={alert.id}>
                    <td>
                      <b>
                        {`${alert.customer_first_names || ""} ${alert.customer_last_names || ""}`.trim() ||
                          "Sin cliente"}
                      </b>
                      <span className="table-detail">
                        {alert.customer_dni ? `DNI ${alert.customer_dni}` : ""}
                      </span>
                    </td>
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
                      <span className={`status ${closed ? "success" : "warning"}`}>
                        {closed ? "Cerrada" : "Seguimiento pendiente"}
                      </span>
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
          </table>
        </div>
        {!data.items.length && !error && (
          <div className="empty-state">
            No hay alertas que coincidan con los filtros seleccionados.
          </div>
        )}
        <Pagination data={data} onPageChange={(page) => load(page).catch(() => setError("No fue posible cargar la página."))} />
      </section>
      {selected && <AlertDetails alert={selected} onClose={() => setSelected(null)} />}
    </>
  );
}
