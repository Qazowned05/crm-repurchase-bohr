import { useEffect, useState } from "react";
import { api } from "../../services/api";
import { StatCard } from "../../components/StatCard";
import { Modal } from "../../components/Modal";
import type { Alert, TypificationTree, User } from "../../services/types";
type Metrics = {
  alerts_considered: number;
  contact_rate: number;
  repurchase_rate: number;
  average_days_between_purchases?: number | null;
};
export function Dashboard({ user }: { user: User }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [typifications, setTypifications] = useState<TypificationTree[]>([]);
  const [parentTypificationId, setParentTypificationId] = useState("");
  const [childTypificationId, setChildTypificationId] = useState("");
  const [managementError, setManagementError] = useState("");
  useEffect(() => {
    api<Alert[]>("/alerts/inbox")
      .then(setAlerts)
      .catch(() => {});
    if (user.role !== "ASESOR") {
      api<Metrics>("/reports/metrics")
        .then(setMetrics)
        .catch(() => {});
      if (user.role === "ADMIN")
        api<User[]>("/users")
          .then(setUsers)
          .catch(() => {});
    }
    if (user.role === "ASESOR")
      api<TypificationTree[]>("/configuration/contact-typifications/tree")
        .then(setTypifications)
        .catch(() => {});
  }, [user.role]);
  const open = alerts.filter((a) =>
    ["PENDIENTE", "REPROGRAMADO", "SIN_RESPUESTA"].includes(a.status),
  );
  const rootTypifications = typifications.filter((item) => item.is_active);
  const selectedParent = rootTypifications.find((item) => item.id === parentTypificationId);
  const childTypifications = selectedParent?.children.filter((item) => item.is_active) || [];
  const selectedChild = childTypifications.find((item) => item.id === childTypificationId);
  const selectedTypification =
    selectedChild || (selectedParent?.children.length === 0 ? selectedParent : undefined);
  const openAlert = async (alert: Alert) => {
    setManagementError("");
    setParentTypificationId("");
    setChildTypificationId("");
    setSelectedAlert(alert);
    try {
      setSelectedAlert(await api<Alert>(`/alerts/${alert.id}`));
    } catch {
      // The inbox payload remains sufficient to inspect and manage the alert.
    }
  };
  const closeAlert = () => {
    setSelectedAlert(null);
    setParentTypificationId("");
    setChildTypificationId("");
    setManagementError("");
  };
  const manageAlert = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAlert || !selectedTypification) return;
    const form = new FormData(event.currentTarget);
    try {
      await api(`/alerts/${selectedAlert.id}/attempts`, {
        method: "POST",
        body: JSON.stringify({
          channel: form.get("channel"),
          result: selectedTypification.code,
          typification_id: selectedTypification.id,
          note: form.get("note") || undefined,
          next_action_date: form.get("next_action_date") || undefined,
        }),
      });
      closeAlert();
      setAlerts(await api<Alert[]>("/alerts/inbox"));
    } catch (reason) {
      setManagementError(
        reason instanceof Error ? reason.message : "No fue posible registrar la gestión.",
      );
    }
  };
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">{user.role === "ASESOR" ? "MI JORNADA" : "SUPERVISION"}</p>
          <h1>Hola, {user.full_name.split(" ")[0]}</h1>
        </div>
        <p>{new Intl.DateTimeFormat("es-PE", { dateStyle: "full" }).format(new Date())}</p>
      </div>
      <section className="stats">
        <StatCard label="Alertas activas" value={open.length} />
        <StatCard
          label="Para hoy"
          value={
            alerts.filter((a) => a.next_action_date === new Date().toISOString().slice(0, 10))
              .length
          }
          accent="orange"
        />
        <StatCard
          label="Atendidas"
          value={alerts.filter((a) => a.attempts_count > 0).length}
          accent="green"
        />
        <StatCard
          label="Tasa de recompra"
          value={metrics ? `${Math.round(metrics.repurchase_rate * 100)}%` : "-"}
          accent="purple"
        />
      </section>
      {user.role !== "ASESOR" && (
        <section className="dashboard-grid">
          <article className="panel">
            <h2>Tipificaciones de atención</h2>
            <div className="bars">
              <i style={{ height: "74%" }} />
              <i style={{ height: "48%" }} />
              <i style={{ height: "61%" }} />
              <i style={{ height: "32%" }} />
            </div>
            <small>Seguimiento &nbsp; Sin respuesta &nbsp; No interesado &nbsp; Otros</small>
          </article>
          <article className="panel">
            <h2>Ventas por recompra</h2>
            <div className="ring">
              <b>{metrics ? `${Math.round(metrics.repurchase_rate * 100)}%` : "0%"}</b>
            </div>
            <p>Conversión de alertas atendidas</p>
          </article>
          <article className="panel advisors">
            <h2>Asesores</h2>
            {users
              .filter((x) => x.role === "ASESOR")
              .slice(0, 5)
              .map((x) => (
                <p key={x.id}>
                  <span className="avatar">{x.full_name[0]}</span>
                  {x.full_name}
                  <small>{x.is_active ? "Activo" : "Inactivo"}</small>
                </p>
              ))}
            {!users.length && <p>La lista de asesores está disponible para administradores.</p>}
          </article>
        </section>
      )}
      {user.role === "ASESOR" ? (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Mis alertas</h2>
              <p>Selecciona una alerta para revisar el cliente y registrar la gestión.</p>
            </div>
            <span className="header-metric">
              <b>{alerts.length}</b> activas
            </span>
          </div>
          <div className="alert-list">
            {alerts.map((alert) => (
              <button className="alert-row" key={alert.id} onClick={() => openAlert(alert)}>
                <span>
                  <b>
                    {alert.customer_first_names} {alert.customer_last_names}
                  </b>
                  <small>
                    {alert.product_name || alert.product_code || "Producto"} · vence{" "}
                    {alert.expected_repurchase_date}
                  </small>
                </span>
                <span className="status warning">{alert.status.replaceAll("_", " ")}</span>
                <span>Gestionar</span>
              </button>
            ))}
            {!alerts.length && <p>No hay alertas activas.</p>}
          </div>
        </section>
      ) : (
        <section className="panel">
          <h2>Próximos vencimientos</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Estado</th>
                  <th>Intentos</th>
                  <th>Asignado</th>
                </tr>
              </thead>
              <tbody>
                {alerts.slice(0, 7).map((a) => (
                  <tr key={a.id}>
                    <td>{a.expected_repurchase_date}</td>
                    <td>
                      <span className="badge">{a.status.replaceAll("_", " ")}</span>
                    </td>
                    <td>{a.attempts_count}</td>
                    <td>{a.assigned_advisor_id ? "Asesor asignado" : "Sin asignar"}</td>
                  </tr>
                ))}
                {!alerts.length && (
                  <tr>
                    <td colSpan={4}>No hay alertas activas.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {selectedAlert && (
        <Modal title="Gestionar alerta" onClose={closeAlert}>
          <div className="alert-detail">
            <p>
              <b>Cliente:</b>{" "}
              {[selectedAlert.customer_first_names, selectedAlert.customer_last_names]
                .filter(Boolean)
                .join(" ") || "Sin información"}
            </p>
            <p>
              <b>Contacto:</b>{" "}
              {[selectedAlert.customer_phone, selectedAlert.customer_email]
                .filter(Boolean)
                .join(" · ") || "Sin información"}
            </p>
            <p>
              <b>Producto:</b>{" "}
              {[
                selectedAlert.product_name,
                selectedAlert.product_brand,
                selectedAlert.product_category,
              ]
                .filter(Boolean)
                .join(" · ") || "Sin información"}
            </p>
            <p>
              <b>Venta original:</b> {selectedAlert.original_sale_date || "Sin información"}
            </p>
            <p>
              <b>Vendedor:</b>{" "}
              {selectedAlert.seller_advisor_name ||
                selectedAlert.seller_advisor_email ||
                "Sin información"}
            </p>
            <p>
              <b>Fecha prevista:</b> {selectedAlert.expected_repurchase_date}
            </p>
          </div>
          <form onSubmit={manageAlert}>
            <div className="form-grid">
              <label>
                Tipificación
                <select
                  value={parentTypificationId}
                  onChange={(event) => {
                    setParentTypificationId(event.target.value);
                    setChildTypificationId("");
                  }}
                  required
                >
                  <option value="">Selecciona una tipificación</option>
                  {rootTypifications.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Subtipificación
                <select
                  value={childTypificationId}
                  onChange={(event) => setChildTypificationId(event.target.value)}
                  disabled={!selectedParent || selectedParent.children.length === 0}
                  required={selectedParent !== undefined && selectedParent.children.length > 0}
                >
                  <option value="">
                    {!selectedParent
                      ? "Selecciona primero una tipificación"
                      : selectedParent.children.length === 0
                        ? "No tiene subtipificaciones"
                        : "Selecciona una subtipificación"}
                  </option>
                  {childTypifications.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Canal de contacto
                <select name="channel" defaultValue="LLAMADA" required>
                  <option value="LLAMADA">Llamada</option>
                  <option value="WHATSAPP">WhatsApp</option>
                  <option value="EMAIL">Correo</option>
                  <option value="OTRO">Otro</option>
                </select>
              </label>
              {selectedTypification?.requires_next_action && (
                <label>
                  Próxima acción
                  <input
                    name="next_action_date"
                    type="date"
                    min={new Date().toISOString().slice(0, 10)}
                    required
                  />
                </label>
              )}
              {selectedTypification?.requires_note && (
                <label className="notes">
                  Nota de gestión
                  <textarea name="note" maxLength={4000} required />
                </label>
              )}
            </div>
            {selectedTypification?.requires_close && (
              <p className="success-message">
                Esta tipificación cerrará la alerta automáticamente.
              </p>
            )}
            {selectedParent?.children.length === 0 && (
              <p className="muted">
                Esta tipificación no tiene subtipificaciones y se registrará como resultado final.
              </p>
            )}
            {!rootTypifications.length && (
              <p className="form-error">
                No hay tipificaciones activas disponibles para gestionar la alerta.
              </p>
            )}
            {managementError && <p className="form-error">{managementError}</p>}
            <footer>
              <button type="button" className="secondary" onClick={closeAlert}>
                Cancelar
              </button>
              <button disabled={!selectedTypification}>Registrar gestión</button>
            </footer>
          </form>
        </Modal>
      )}
    </>
  );
}
