import { useEffect, useState } from "react";
import { Modal } from "../../components/Modal";
import { SearchSelect } from "../../components/SearchSelect";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import { api, listAll } from "../../services/api";
import type {
  ContactAttempt,
  ManagedAlert,
  Paged,
  Product,
  TypificationTree,
  User,
} from "../../services/types";

const closedStatuses = new Set([
  "RECOMPRA_LOGRADA",
  "COMPRA_OTRO_PRODUCTO",
  "CERRADO_POR_TIPIFICACION",
  "CANCELADO_POR_RECOMPRA",
  "CANCELADO_POR_ANULACION",
  "NO_INTERESADO",
  "VENCIDO_NO_GESTIONADO",
]);
type RepurchaseSelection = "ORIGINAL" | "OTHER" | "BOTH";
type RepurchaseLine = { product_id: string; quantity: number };

function formatDate(value?: string | null, withTime = false) {
  if (!value) return "Sin registro";
  const date = new Date(withTime ? value : `${value}T00:00:00`);
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" } : {}),
  }).format(date);
}

function daysOverdue(value: string) {
  return Math.max(0, Math.floor((Date.now() - new Date(`${value}T00:00:00`).getTime()) / 86400000));
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

function closureDetail(alert: ManagedAlert) {
  if (alert.status === "RECOMPRA_LOGRADA") return null;
  if (alert.closure_reason?.startsWith("TIPIFICACION_DE_CIERRE: ")) {
    return alert.closure_reason.replace("TIPIFICACION_DE_CIERRE: ", "");
  }
  if (alert.closure_reason === "VENTA_ORIGINAL_ANULADA") return "Venta original anulada";
  if (alert.closure_reason === "CIERRE_MANUAL") return "Cierre manual";
  return null;
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
        <div>
          <span>Enfermedad o condición</span>
          <b>{alert.customer_condition || "Sin información"}</b>
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

function AlertManagement({
  alert,
  typifications,
  products,
  onClose,
  onManaged,
}: {
  alert: ManagedAlert;
  typifications: TypificationTree[];
  products: Product[];
  onClose: () => void;
  onManaged: () => Promise<void>;
}) {
  const [mode, setMode] = useState<"ATTEMPT" | "REPURCHASE">("ATTEMPT");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [repurchaseSelection, setRepurchaseSelection] = useState<RepurchaseSelection>("ORIGINAL");
  const [originalQuantity, setOriginalQuantity] = useState(1);
  const [extraLines, setExtraLines] = useState<RepurchaseLine[]>([]);
  const options = typifications.flatMap((parent) => [
    { id: parent.id, code: parent.code, label: parent.name },
    ...parent.children.map((child) => ({
      id: child.id,
      code: child.code,
      label: `${parent.name} / ${child.name}`,
    })),
  ]);
  return (
    <Modal title="Gestionar alerta" onClose={onClose}>
      <div className="alert-summary">
        <div>
          <span>Cliente</span>
          <b>{`${alert.customer_first_names || ""} ${alert.customer_last_names || ""}`.trim()}</b>
          <small>{alert.customer_dni ? `DNI ${alert.customer_dni}` : ""}</small>
        </div>
        <div>
          <span>Producto</span>
          <b>{alert.product_name || "Sin producto"}</b>
          <small>{alert.product_code || ""}</small>
        </div>
      </div>
      <form
        className="alert-management-form"
        onSubmit={async (event) => {
          event.preventDefault();
          setError("");
          setSaving(true);
          const form = new FormData(event.currentTarget);
          try {
            if (mode === "REPURCHASE") {
              if (!alert.product_id) throw new Error("La alerta no tiene un producto válido.");
              const items = [
                ...(repurchaseSelection === "ORIGINAL" || repurchaseSelection === "BOTH"
                  ? [{ product_id: alert.product_id, quantity: originalQuantity }]
                  : []),
                ...(repurchaseSelection === "OTHER" || repurchaseSelection === "BOTH"
                  ? extraLines
                  : []),
              ];
              if (!items.length || items.some((item) => !item.product_id || item.quantity <= 0)) {
                throw new Error("Completa producto y cantidad para cada producto confirmado.");
              }
              await api(`/alerts/${alert.id}/repurchase`, {
                method: "POST",
                body: JSON.stringify({
                  sale_date: form.get("sale_date"),
                  notes: form.get("notes") || undefined,
                  customer_condition: form.get("customer_condition") || undefined,
                  items,
                }),
              });
            } else {
              const option = options.find((item) => item.id === form.get("typification_id"));
              if (!option) throw new Error("Selecciona una tipificación.");
              await api(`/alerts/${alert.id}/attempts`, {
                method: "POST",
                body: JSON.stringify({
                  channel: form.get("channel"),
                  result: option.code,
                  typification_id: option.id,
                  note: form.get("note") || undefined,
                  next_action_date: form.get("next_action_date") || undefined,
                }),
              });
            }
            await onManaged();
            onClose();
          } catch (reason) {
            setError(
              reason instanceof Error ? reason.message : "No fue posible registrar la gestión.",
            );
          } finally {
            setSaving(false);
          }
        }}
      >
        <fieldset className="management-mode-switch">
          <legend>Resultado de la gestión</legend>
          <label className={mode === "ATTEMPT" ? "is-selected" : ""}>
            <input type="radio" checked={mode === "ATTEMPT"} onChange={() => setMode("ATTEMPT")} />
            Tipificar contacto
          </label>
          <label className={mode === "REPURCHASE" ? "is-selected" : ""}>
            <input
              type="radio"
              checked={mode === "REPURCHASE"}
              onChange={() => setMode("REPURCHASE")}
            />
            Recompra confirmada
          </label>
        </fieldset>
        {mode === "ATTEMPT" ? (
          <div className="form-grid">
            <label>
              Tipificación
              <select name="typification_id" required defaultValue="">
                <option value="" disabled>
                  Selecciona una tipificación
                </option>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Canal
              <select name="channel" required defaultValue="LLAMADA">
                <option value="LLAMADA">Llamada</option>
                <option value="WHATSAPP">WhatsApp</option>
                <option value="EMAIL">Correo</option>
                <option value="OTRO">Otro</option>
              </select>
            </label>
            <label>
              Próxima acción
              <input name="next_action_date" type="date" />
            </label>
            <label className="notes">
              Nota
              <textarea name="note" maxLength={4000} />
            </label>
          </div>
        ) : (
          <section className="repurchase-confirmation" aria-label="Detalle de la recompra">
            <p className="repurchase-info-banner">
              Registra la venta confirmada. Esta acción cerrará la alerta y no requiere
              tipificación.
            </p>
            {repurchaseSelection === "OTHER" && (
              <p className="repurchase-info-banner repurchase-recovery-note">
                La alerta del producto original quedará en recuperación para seguimiento posterior.
              </p>
            )}
            <fieldset className="repurchase-product-choice">
              <legend>¿Qué compró?</legend>
              <div>
                {(
                  [
                    ["ORIGINAL", "Original"],
                    ["OTHER", "Otro producto"],
                    ["BOTH", "Ambos"],
                  ] as Array<[RepurchaseSelection, string]>
                ).map(([value, label]) => (
                  <label key={value} className={repurchaseSelection === value ? "is-selected" : ""}>
                    <input
                      type="radio"
                      name="repurchase-selection"
                      value={value}
                      checked={repurchaseSelection === value}
                      onChange={() => setRepurchaseSelection(value)}
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
            {(repurchaseSelection === "ORIGINAL" || repurchaseSelection === "BOTH") && (
              <section className="repurchase-original-line">
                <div className="repurchase-line-product">
                  <span>Producto original</span>
                  <b>{alert.product_name || alert.product_code || "Sin información"}</b>
                </div>
                <label>
                  Cantidad
                  <input
                    type="number"
                    min="1"
                    value={originalQuantity}
                    onChange={(event) => setOriginalQuantity(Number(event.target.value))}
                    required
                  />
                </label>
              </section>
            )}
            {(repurchaseSelection === "OTHER" || repurchaseSelection === "BOTH") && (
              <section className="repurchase-extra-products">
                <div className="repurchase-section-heading">
                  <h3>Otros productos</h3>
                  <button
                    type="button"
                    className="secondary repurchase-add-product"
                    onClick={() =>
                      setExtraLines((lines) => [...lines, { product_id: "", quantity: 1 }])
                    }
                  >
                    Agregar producto
                  </button>
                </div>
                {extraLines.map((line, index) => (
                  <div className="repurchase-extra-line" key={index}>
                    <label>
                      Producto
                      <SearchSelect
                        value={line.product_id}
                        placeholder="Busca por nombre o código"
                        required
                        onChange={(product_id) =>
                          setExtraLines((lines) =>
                            lines.map((item, lineIndex) =>
                              lineIndex === index ? { ...item, product_id } : item,
                            ),
                          )
                        }
                        options={products
                          .filter(
                            (product) =>
                              product.id !== alert.product_id &&
                              !extraLines.some(
                                (item, lineIndex) =>
                                  lineIndex !== index && item.product_id === product.id,
                              ),
                          )
                          .map((product) => ({
                            value: product.id,
                            label: `${product.name} (${product.code})`,
                          }))}
                      />
                    </label>
                    <label>
                      Cantidad
                      <input
                        type="number"
                        min="1"
                        value={line.quantity}
                        onChange={(event) =>
                          setExtraLines((lines) =>
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
                    <button
                      type="button"
                      className="secondary repurchase-remove-product"
                      onClick={() =>
                        setExtraLines((lines) =>
                          lines.filter((_, lineIndex) => lineIndex !== index),
                        )
                      }
                    >
                      Quitar
                    </button>
                  </div>
                ))}
                {!extraLines.length && (
                  <p className="repurchase-empty-lines">Agrega los productos confirmados.</p>
                )}
              </section>
            )}
            <div className="form-grid">
              <label>
                Fecha de recompra
                <input
                  name="sale_date"
                  type="date"
                  defaultValue={new Date().toISOString().slice(0, 10)}
                  required
                />
              </label>
              <label className="notes">
                Enfermedad o condición del cliente
                <textarea
                  name="customer_condition"
                  defaultValue={alert.customer_condition || ""}
                  maxLength={500}
                  placeholder="Actualiza solo si hubo cambios"
                />
              </label>
              <label className="notes">
                Nota
                <textarea name="notes" maxLength={4000} />
              </label>
            </div>
          </section>
        )}
        {error && <p className="form-error">{error}</p>}
        <footer>
          <button type="button" className="secondary" onClick={onClose} disabled={saving}>
            Cancelar
          </button>
          <button disabled={saving}>{saving ? "Guardando..." : "Guardar gestión"}</button>
        </footer>
      </form>
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
  const [managing, setManaging] = useState<ManagedAlert | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [advisors, setAdvisors] = useState<User[]>([]);
  const [typifications, setTypifications] = useState<TypificationTree[]>([]);
  const [filters, setFilters] = useState({
    date_from: "",
    date_to: "",
    state: "",
    q: "",
    product_id: "",
    status: "",
    alert_type: "",
    advisor_id: "",
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
    listAll<Product>("/products")
      .then(setProducts)
      .catch(() => {});
    api<User[]>("/users/advisors")
      .then(setAdvisors)
      .catch(() => {});
    api<TypificationTree[]>("/configuration/contact-typifications/tree")
      .then(setTypifications)
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
                advisor_id: "",
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
            {advisors.length > 0 && (
              <label>
                Asesor
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
                <option value="CERRADO_POR_TIPIFICACION">Cerrada por tipificación</option>
                <option value="RECOMPRA_LOGRADA">Recompra lograda</option>
                <option value="NO_INTERESADO">No interesado</option>
                <option value="CANCELADO_POR_RECOMPRA">Cancelada por recompra</option>
                <option value="CANCELADO_POR_ANULACION">Cancelada por anulación</option>
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
                <tbody
                  className="alert-register-customer"
                  key={customer.customer_id || customer.id}
                >
                  {customerAlerts.map((alert, index) => {
                    const latest = latestAttempt(alert);
                    const closed = closedStatuses.has(alert.status);
                    return (
                      <tr
                        key={alert.id}
                        className={closed ? "" : "alert-table-row is-actionable"}
                        role={closed ? undefined : "button"}
                        tabIndex={closed ? undefined : 0}
                        aria-label={
                          closed
                            ? undefined
                            : `Gestionar alerta de ${alert.product_name || "producto"}`
                        }
                        onClick={closed ? undefined : () => setManaging(alert)}
                        onKeyDown={
                          closed
                            ? undefined
                            : (event) => {
                                if (event.key === "Enter" || event.key === " ") {
                                  event.preventDefault();
                                  setManaging(alert);
                                }
                              }
                        }
                      >
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
                              {customerAlerts.length}{" "}
                              {customerAlerts.length === 1 ? "alerta" : "alertas"}
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
                          <span className="table-detail">
                            Alerta: {formatDate(alert.alert_date)}
                          </span>
                          {!closed && daysOverdue(alert.alert_date) > 0 && (
                            <span className="table-detail danger-text">
                              Atención vencida: {daysOverdue(alert.alert_date)} días
                            </span>
                          )}
                        </td>
                        <td>
                          <span className={alertStatusClass(alert.status)}>
                            {statusLabel(alert.status)}
                          </span>
                          <span className="table-detail">
                            {closed
                              ? closureDetail(alert) || latest?.observation || latest?.note
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
                          <div className="row-actions">
                            <button
                              className="link"
                              onClick={(event) => {
                                event.stopPropagation();
                                setSelected(alert);
                              }}
                            >
                              Ver detalle
                            </button>
                          </div>
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
      {managing && (
        <AlertManagement
          alert={managing}
          typifications={typifications}
          products={products}
          onClose={() => setManaging(null)}
          onManaged={() => load(data.page)}
        />
      )}
    </>
  );
}
