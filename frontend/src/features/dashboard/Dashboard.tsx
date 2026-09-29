import { useEffect, useState } from "react";
import { api } from "../../services/api";
import { StatCard } from "../../components/StatCard";
import { Modal } from "../../components/Modal";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import type {
  Alert,
  AlertRepurchaseCreate,
  Metrics,
  Paged,
  Product,
  RepurchaseItem,
  TypificationTree,
  User,
} from "../../services/types";

type RepurchaseSelection = "ORIGINAL" | "OTHER" | "BOTH";
type ExtraRepurchaseLine = RepurchaseItem;

export function Dashboard({ user }: { user: User }) {
  const [alertPage, setAlertPage] = useState<Paged<Alert>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
    pages: 0,
  });
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [typifications, setTypifications] = useState<TypificationTree[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [parentTypificationId, setParentTypificationId] = useState("");
  const [childTypificationId, setChildTypificationId] = useState("");
  const [managementMode, setManagementMode] = useState<"ATTEMPT" | "REPURCHASE">("ATTEMPT");
  const [repurchaseSelection, setRepurchaseSelection] = useState<RepurchaseSelection>("ORIGINAL");
  const [originalRepurchase, setOriginalRepurchase] = useState<RepurchaseItem>({
    product_id: "",
    quantity: 1,
    unit_price: 0,
  });
  const [extraRepurchaseLines, setExtraRepurchaseLines] = useState<ExtraRepurchaseLine[]>([]);
  const [managementError, setManagementError] = useState("");
  const [managementSuccess, setManagementSuccess] = useState("");
  const [alertError, setAlertError] = useState("");
  useEffect(() => {
    api<Paged<Alert> | Alert[]>(`/alerts/inbox?page=1&page_size=${PAGE_SIZE}`)
      .then((value) => setAlertPage(asPaged(value)))
      .catch(() => setAlertError("No es posible mostrar las alertas en este momento."));
    if (user.role !== "ASESOR") {
      api<Metrics>("/reports/metrics")
        .then(setMetrics)
        .catch(() => {});
    }
    if (user.role === "ASESOR") {
      api<TypificationTree[]>("/configuration/contact-typifications/tree")
        .then(setTypifications)
        .catch(() => {});
      api<Paged<Product> | Product[]>("/products?page=1&page_size=200")
        .then((value) => setProducts(asPaged(value).items.filter((product) => product.is_active)))
        .catch(() => {});
    }
  }, [user.role]);
  const alerts = alertPage.items;
  const loadAlerts = (page: number) =>
    api<Paged<Alert> | Alert[]>(`/alerts/inbox?page=${page}&page_size=${PAGE_SIZE}`).then((value) =>
      setAlertPage(asPaged(value, page)),
    );
  const rootTypifications = typifications.filter((item) => item.is_active);
  const selectedParent = rootTypifications.find((item) => item.id === parentTypificationId);
  const childTypifications = selectedParent?.children.filter((item) => item.is_active) || [];
  const selectedChild = childTypifications.find((item) => item.id === childTypificationId);
  const selectedTypification =
    selectedChild || (selectedParent?.children.length === 0 ? selectedParent : undefined);
  const openAlert = async (alert: Alert) => {
    setManagementError("");
    setManagementSuccess("");
    setParentTypificationId("");
    setChildTypificationId("");
    setManagementMode("ATTEMPT");
    setRepurchaseSelection("ORIGINAL");
    setOriginalRepurchase({ product_id: alert.product_id || "", quantity: 1, unit_price: 0 });
    setExtraRepurchaseLines([]);
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
    setManagementMode("ATTEMPT");
    setExtraRepurchaseLines([]);
    setManagementError("");
  };
  const manageAlert = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedAlert) return;
    const form = new FormData(event.currentTarget);
    try {
      if (managementMode === "REPURCHASE") {
        const items = [
          ...(repurchaseSelection === "ORIGINAL" || repurchaseSelection === "BOTH"
            ? [originalRepurchase]
            : []),
          ...(repurchaseSelection === "OTHER" || repurchaseSelection === "BOTH"
            ? extraRepurchaseLines
            : []),
        ];
        if (
          !items.length ||
          items.some((item) => !item.product_id || item.quantity <= 0 || item.unit_price <= 0)
        ) {
          setManagementError(
            "Completa producto, cantidad y precio unitario para cada línea de recompra.",
          );
          return;
        }
        if (new Set(items.map((item) => item.product_id)).size !== items.length) {
          setManagementError("Un producto solo puede incluirse una vez en la recompra.");
          return;
        }
        const payload: AlertRepurchaseCreate = { items };
        await api(`/alerts/${selectedAlert.id}/repurchase`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      } else {
        if (!selectedTypification) return;
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
      }
      setManagementSuccess(
        managementMode === "REPURCHASE"
          ? "Recompra confirmada y alerta cerrada correctamente."
          : "Gestión registrada correctamente.",
      );
      closeAlert();
      await loadAlerts(alertPage.page);
      if (user.role !== "ASESOR")
        api<Metrics>("/reports/metrics")
          .then(setMetrics)
          .catch(() => {});
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
      {managementSuccess && <p className="success-message">{managementSuccess}</p>}
      <section className="stats">
        <StatCard
          label="Alertas activas"
          value={metrics ? metrics.alerts_considered : alertPage.total}
        />
        <StatCard
          label={metrics ? "Gestionadas" : "Para hoy"}
          value={
            metrics
              ? metrics.advisor_ranking.reduce(
                  (total, advisor) => total + advisor.managed_alerts,
                  0,
                )
              : alerts.filter((a) => a.next_action_date === new Date().toISOString().slice(0, 10))
                  .length
          }
          accent="orange"
        />
        <StatCard
          label="Atendidas"
          value={
            metrics
              ? metrics.repurchase_denominator
              : alerts.filter((a) => a.attempts_count > 0).length
          }
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
              {(metrics?.attention_typifications || []).map((item) => (
                <i
                  key={item.typification_id}
                  title={`${item.typification_name}: ${item.attempts}`}
                  style={{
                    height: `${Math.max(8, (item.attempts / Math.max(...(metrics?.attention_typifications.map((x) => x.attempts) || [1]))) * 100)}%`,
                  }}
                />
              ))}
            </div>
            <small>
              {metrics?.attention_typifications
                .map((item) => `${item.typification_name} (${item.attempts})`)
                .join(" · ") || "Sin gestiones tipificadas"}
            </small>
          </article>
          <article className="panel">
            <h2>Ventas por recompra</h2>
            <div className="ring">
              <b>{metrics ? `${Math.round(metrics.repurchase_rate * 100)}%` : "0%"}</b>
            </div>
            <p>Conversión de alertas atendidas</p>
          </article>
          <article className="panel advisors">
            <h2>Ranking de asesores</h2>
            {metrics?.advisor_ranking.slice(0, 5).map((advisor) => (
              <p key={advisor.advisor_id}>
                <span className="avatar">{advisor.advisor_name[0]}</span>
                {advisor.advisor_name}
                <small>
                  {advisor.confirmed_repurchases} recompras · {advisor.managed_alerts} gestionadas
                </small>
              </p>
            ))}
            {!metrics?.advisor_ranking.length && <p>No hay actividad de asesores en el periodo.</p>}
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
                  <small>
                    {alert.alert_type?.replaceAll("_", " ") || "AUTOMÁTICA"}
                    {alert.assignment_reason ? ` · ${alert.assignment_reason}` : ""}
                    {alert.next_action_date ? ` · Próxima acción: ${alert.next_action_date}` : ""}
                  </small>
                </span>
                <span className="status warning">{alert.status.replaceAll("_", " ")}</span>
                <span>Gestionar</span>
              </button>
            ))}
            {!alerts.length && <p>No hay alertas activas.</p>}
            {alertError && <p className="form-error">{alertError}</p>}
          </div>
          <Pagination data={alertPage} onPageChange={(page) => loadAlerts(page).catch(() => {})} />
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
          <Pagination data={alertPage} onPageChange={(page) => loadAlerts(page).catch(() => {})} />
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
            <p>
              <b>Tipo de alerta:</b>{" "}
              {selectedAlert.alert_type?.replaceAll("_", " ") || "AUTOMÁTICA"}
            </p>
            {selectedAlert.assignment_reason && (
              <p>
                <b>Motivo de asignación:</b> {selectedAlert.assignment_reason}
              </p>
            )}
            {selectedAlert.next_action_date && (
              <p>
                <b>Próxima acción:</b> {selectedAlert.next_action_date}
              </p>
            )}
          </div>
          <form onSubmit={manageAlert}>
            <fieldset className="management-mode-switch">
              <legend>Resultado de la gestión</legend>
              <label className={managementMode === "ATTEMPT" ? "is-selected" : ""}>
                <input
                  type="radio"
                  checked={managementMode === "ATTEMPT"}
                  onChange={() => {
                    setManagementMode("ATTEMPT");
                    setManagementError("");
                  }}
                />
                Gestión regular
              </label>
              <label className={managementMode === "REPURCHASE" ? "is-selected" : ""}>
                <input
                  type="radio"
                  checked={managementMode === "REPURCHASE"}
                  onChange={() => {
                    setManagementMode("REPURCHASE");
                    setManagementError("");
                  }}
                />
                Recompra confirmada
              </label>
            </fieldset>
            {managementMode === "REPURCHASE" ? (
              <section className="repurchase-confirmation" aria-label="Detalle de la recompra">
                <p className="repurchase-info-banner">
                  Registra la venta confirmada. Esta acción cerrará la alerta y no requiere
                  tipificación.
                </p>
                <fieldset className="repurchase-product-choice">
                  <legend>¿Qué compró?</legend>
                  <div>
                    <label className={repurchaseSelection === "ORIGINAL" ? "is-selected" : ""}>
                      <input
                        type="radio"
                        name="repurchase-selection"
                        value="ORIGINAL"
                        checked={repurchaseSelection === "ORIGINAL"}
                        onChange={(event) =>
                          setRepurchaseSelection(event.target.value as RepurchaseSelection)
                        }
                      />
                      Original
                    </label>
                    <label className={repurchaseSelection === "OTHER" ? "is-selected" : ""}>
                      <input
                        type="radio"
                        name="repurchase-selection"
                        value="OTHER"
                        checked={repurchaseSelection === "OTHER"}
                        onChange={(event) =>
                          setRepurchaseSelection(event.target.value as RepurchaseSelection)
                        }
                      />
                      Otro producto
                    </label>
                    <label className={repurchaseSelection === "BOTH" ? "is-selected" : ""}>
                      <input
                        type="radio"
                        name="repurchase-selection"
                        value="BOTH"
                        checked={repurchaseSelection === "BOTH"}
                        onChange={(event) =>
                          setRepurchaseSelection(event.target.value as RepurchaseSelection)
                        }
                      />
                      Ambos
                    </label>
                  </div>
                </fieldset>
                {(repurchaseSelection === "ORIGINAL" || repurchaseSelection === "BOTH") && (
                  <section
                    className="repurchase-original-line"
                    aria-labelledby="original-product-title"
                  >
                    <div className="repurchase-line-product">
                      <span id="original-product-title">Producto original</span>
                      <b>
                        {selectedAlert.product_name ||
                          selectedAlert.product_code ||
                          "Sin información"}
                      </b>
                    </div>
                    <label>
                      Cantidad
                      <input
                        type="number"
                        min="1"
                        step="1"
                        value={originalRepurchase.quantity}
                        onChange={(event) =>
                          setOriginalRepurchase((line) => ({
                            ...line,
                            quantity: Number(event.target.value),
                          }))
                        }
                        required
                      />
                    </label>
                    <label>
                      Precio unitario
                      <input
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={originalRepurchase.unit_price || ""}
                        onChange={(event) =>
                          setOriginalRepurchase((line) => ({
                            ...line,
                            unit_price: Number(event.target.value),
                          }))
                        }
                        required
                      />
                    </label>
                  </section>
                )}
                {(repurchaseSelection === "OTHER" || repurchaseSelection === "BOTH") && (
                  <section
                    className="repurchase-extra-products"
                    aria-labelledby="extra-products-title"
                  >
                    <div className="repurchase-section-heading">
                      <h3 id="extra-products-title">Otros productos</h3>
                      <button
                        type="button"
                        className="secondary repurchase-add-product"
                        onClick={() =>
                          setExtraRepurchaseLines((lines) => [
                            ...lines,
                            { product_id: "", quantity: 1, unit_price: 0 },
                          ])
                        }
                      >
                        Agregar producto
                      </button>
                    </div>
                    {extraRepurchaseLines.map((line, index) => (
                      <div className="repurchase-extra-line" key={index}>
                        <label>
                          Producto
                          <select
                            value={line.product_id}
                            onChange={(event) =>
                              setExtraRepurchaseLines((lines) =>
                                lines.map((item, lineIndex) =>
                                  lineIndex === index
                                    ? { ...item, product_id: event.target.value }
                                    : item,
                                ),
                              )
                            }
                            required
                          >
                            <option value="">Selecciona un producto</option>
                            {products.map((product) => (
                              <option
                                key={product.id}
                                value={product.id}
                                disabled={
                                  product.id === selectedAlert.product_id ||
                                  extraRepurchaseLines.some(
                                    (item, lineIndex) =>
                                      lineIndex !== index && item.product_id === product.id,
                                  )
                                }
                              >
                                {product.name} ({product.code})
                              </option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Cantidad
                          <input
                            type="number"
                            min="1"
                            step="1"
                            value={line.quantity}
                            onChange={(event) =>
                              setExtraRepurchaseLines((lines) =>
                                lines.map((item, lineIndex) =>
                                  lineIndex === index
                                    ? { ...item, quantity: Number(event.target.value) }
                                    : item,
                                ),
                              )
                            }
                            required
                          />
                        </label>
                        <label>
                          Precio unitario
                          <input
                            type="number"
                            min="0.01"
                            step="0.01"
                            value={line.unit_price || ""}
                            onChange={(event) =>
                              setExtraRepurchaseLines((lines) =>
                                lines.map((item, lineIndex) =>
                                  lineIndex === index
                                    ? { ...item, unit_price: Number(event.target.value) }
                                    : item,
                                ),
                              )
                            }
                            required
                          />
                        </label>
                        <button
                          type="button"
                          className="secondary repurchase-remove-product"
                          onClick={() =>
                            setExtraRepurchaseLines((lines) =>
                              lines.filter((_, lineIndex) => lineIndex !== index),
                            )
                          }
                        >
                          Quitar
                        </button>
                      </div>
                    ))}
                    {!extraRepurchaseLines.length && (
                      <p className="repurchase-empty-lines">Agrega los productos confirmados.</p>
                    )}
                  </section>
                )}
              </section>
            ) : (
              <>
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
                    Esta tipificación no tiene subtipificaciones y se registrará como resultado
                    final.
                  </p>
                )}
                {!rootTypifications.length && (
                  <p className="form-error">
                    No hay tipificaciones activas disponibles para gestionar la alerta.
                  </p>
                )}
              </>
            )}
            {managementError && <p className="form-error">{managementError}</p>}
            <footer>
              <button type="button" className="secondary" onClick={closeAlert}>
                Cancelar
              </button>
              <button disabled={managementMode === "ATTEMPT" && !selectedTypification}>
                {managementMode === "REPURCHASE" ? "Confirmar recompra" : "Registrar gestión"}
              </button>
            </footer>
          </form>
        </Modal>
      )}
    </>
  );
}
