import { memo, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, listAll } from "../../services/api";
import { StatCard } from "../../components/StatCard";
import { Modal } from "../../components/Modal";
import { SearchSelect } from "../../components/SearchSelect";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import type {
  Alert,
  AlertRepurchaseCreate,
  AdvisorSalesMetrics,
  Metrics,
  ManagedAlert,
  Paged,
  Product,
  RepurchaseItem,
  TypificationTree,
  UpcomingAlert,
  User,
} from "../../services/types";

type RepurchaseSelection = "ORIGINAL" | "OTHER" | "BOTH";
type ExtraRepurchaseLine = RepurchaseItem;
type AlertSummary = { total: number; unmanaged: number; due_today: number; overdue: number };

function alertStatusClass(status: string) {
  return `status alert-status-${status.toLowerCase().replaceAll("_", "-")}`;
}

function formatAlertDate(value?: string | null, withTime = false) {
  if (!value) return "Sin registro";
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" } : {}),
  }).format(new Date(withTime ? value : `${value}T00:00:00`));
}

function latestAlertAttempt(alert: ManagedAlert) {
  return alert.contact_attempts[alert.contact_attempts.length - 1];
}

function formatCurrency(value: string | number) {
  return new Intl.NumberFormat("es-PE", {
    style: "currency",
    currency: "PEN",
    minimumFractionDigits: 2,
  }).format(Number(value));
}

function daysSince(date?: string | null) {
  if (!date) return "-";
  return Math.max(0, Math.floor((Date.now() - new Date(`${date}T00:00:00`).getTime()) / 86400000));
}

function daysOverdue(date?: string | null) {
  return date
    ? Math.max(0, Math.floor((Date.now() - new Date(`${date}T00:00:00`).getTime()) / 86400000))
    : 0;
}

function advisorInitials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function advisorAvatarTone(name: string) {
  return name.charCodeAt(0) % 5;
}

export const Dashboard = memo(function Dashboard({ user }: { user: User }) {
  const currentMonthStart = `${new Date().toISOString().slice(0, 8)}01`;
  const [alertPage, setAlertPage] = useState<Paged<ManagedAlert>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
    pages: 0,
  });
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [metricsPeriod, setMetricsPeriod] = useState(() => {
    const today = new Date();
    const year = today.getFullYear();
    const month = String(today.getMonth() + 1).padStart(2, "0");
    const lastDay = new Date(year, today.getMonth() + 1, 0).getDate();
    return { start_date: `${year}-${month}-01`, end_date: `${year}-${month}-${lastDay}` };
  });
  const [advisorMetrics, setAdvisorMetrics] = useState<AdvisorSalesMetrics | null>(null);
  const [upcomingAlerts, setUpcomingAlerts] = useState<UpcomingAlert[]>([]);
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
  });
  const [extraRepurchaseLines, setExtraRepurchaseLines] = useState<ExtraRepurchaseLine[]>([]);
  const [managementError, setManagementError] = useState("");
  const [managementSuccess, setManagementSuccess] = useState("");
  const [alertError, setAlertError] = useState("");
  const [alertSummary, setAlertSummary] = useState<AlertSummary>({
    total: 0,
    unmanaged: 0,
    due_today: 0,
    overdue: 0,
  });
  const [alertFilters, setAlertFilters] = useState({ q: "", status: "", priority: "" });
  const loadMetrics = (period = metricsPeriod) => {
    const query = new URLSearchParams(period);
    return api<Metrics>(`/reports/metrics?${query}`).then(setMetrics);
  };
  useEffect(() => {
    loadAlerts(1).catch(() => setAlertError("No es posible mostrar las alertas en este momento."));
    if (user.role !== "ASESOR") {
      loadMetrics().catch(() => {});
    }
    if (user.role === "ASESOR") {
      api<AdvisorSalesMetrics>(`/sales/me/metrics?date_from=${currentMonthStart}`)
        .then(setAdvisorMetrics)
        .catch(() => {});
      api<TypificationTree[]>("/configuration/contact-typifications/tree")
        .then(setTypifications)
        .catch(() => {});
      listAll<Product>("/products")
        .then((value) => setProducts(value.filter((product) => product.is_active)))
        .catch(() => {});
      api<UpcomingAlert[]>("/alerts/upcoming")
        .then(setUpcomingAlerts)
        .catch(() => {});
    }
  }, [user.role]);
  const alerts = alertPage.items;
  const alertsByCustomer = new Map<string, ManagedAlert[]>();
  alerts.forEach((alert) => {
    const customerKey = alert.customer_id || alert.customer_dni || alert.id;
    alertsByCustomer.set(customerKey, [...(alertsByCustomer.get(customerKey) || []), alert]);
  });
  const loadAlerts = (page = 1, active = alertFilters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    return api<Paged<ManagedAlert> | ManagedAlert[]>(`/alerts/inbox?${query}`).then((alerts) => {
      setAlertPage(asPaged(alerts, page));
      return api<AlertSummary>(`/alerts/inbox-summary?${query}`)
        .then(setAlertSummary)
        .catch(() => {});
    });
  };
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
    setOriginalRepurchase({ product_id: alert.product_id || "", quantity: 1 });
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
        if (!items.length || items.some((item) => !item.product_id || item.quantity <= 0)) {
          setManagementError("Completa producto y cantidad para cada línea de recompra.");
          return;
        }
        if (new Set(items.map((item) => item.product_id)).size !== items.length) {
          setManagementError("Un producto solo puede incluirse una vez en la recompra.");
          return;
        }
        const payload: AlertRepurchaseCreate = {
          items,
          customer_condition: String(form.get("customer_condition") || "") || undefined,
        };
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
      if (user.role === "ASESOR")
        api<AdvisorSalesMetrics>(`/sales/me/metrics?date_from=${currentMonthStart}`)
          .then(setAdvisorMetrics)
          .catch(() => {});
      else loadMetrics().catch(() => {});
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
        <div className="dashboard-date-controls">
          <p>{new Intl.DateTimeFormat("es-PE", { dateStyle: "full" }).format(new Date())}</p>
          {user.role !== "ASESOR" && (
            <form
              className="dashboard-period"
              onSubmit={(event) => {
                event.preventDefault();
                loadMetrics().catch(() => {});
              }}
            >
              <label>
                Desde
                <input
                  type="date"
                  value={metricsPeriod.start_date}
                  onChange={(event) =>
                    setMetricsPeriod((period) => ({ ...period, start_date: event.target.value }))
                  }
                />
              </label>
              <label>
                Hasta
                <input
                  type="date"
                  value={metricsPeriod.end_date}
                  onChange={(event) =>
                    setMetricsPeriod((period) => ({ ...period, end_date: event.target.value }))
                  }
                />
              </label>
              <button type="submit">Aplicar</button>
            </form>
          )}
        </div>
      </div>
      {managementSuccess && <p className="success-message">{managementSuccess}</p>}
      {user.role !== "ASESOR" && (
        <section className="stats supervisor-stats">
          <StatCard
            label="Facturación total"
            value={metrics ? formatCurrency(metrics.total_revenue) : "-"}
            accent="green"
          />
          <StatCard
            label="Ingreso por recompra"
            value={metrics ? formatCurrency(metrics.repurchase_revenue) : "-"}
            accent="purple"
          />
          <StatCard label="Unidades vendidas" value={metrics ? metrics.total_units_sold : "-"} />
          <StatCard
            label="Ticket promedio"
            value={metrics ? formatCurrency(metrics.average_ticket) : "-"}
            accent="orange"
          />
        </section>
      )}
      {user.role !== "ASESOR" && (
        <section className="dashboard-grid supervisor-dashboard-grid">
          <article className="panel">
            <h2>Ventas por producto</h2>
            {metrics?.top_products_by_units.length ? (
              <div className="product-chart product-ranking-chart">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    layout="vertical"
                    data={metrics.top_products_by_units}
                    margin={{ top: 4, right: 32, left: 8, bottom: 0 }}
                  >
                    <CartesianGrid stroke="#dce5ec" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} hide />
                    <YAxis
                      dataKey="product_name"
                      type="category"
                      width={130}
                      tick={{ fill: "#526b7d", fontSize: 11 }}
                    />
                    <Tooltip
                      cursor={{ fill: "#f0f6fa" }}
                      formatter={(value) => [`${value} uds.`, "Unidades"]}
                    />
                    <Bar dataKey="units" fill="#005a9c" radius={[0, 2, 2, 0]}>
                      <LabelList
                        dataKey="units"
                        position="right"
                        formatter={(value) => `${value} uds.`}
                        fill="#29475e"
                        fontSize={11}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p>Sin ventas registradas.</p>
            )}
          </article>
          <article className="panel">
            <h2>Facturación por producto</h2>
            {metrics?.top_products_by_revenue.length ? (
              <div className="product-chart product-ranking-chart">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart
                    layout="vertical"
                    data={metrics.top_products_by_revenue}
                    margin={{ top: 4, right: 50, left: 8, bottom: 0 }}
                  >
                    <CartesianGrid stroke="#dce5ec" horizontal={false} />
                    <XAxis type="number" hide />
                    <YAxis
                      dataKey="product_name"
                      type="category"
                      width={130}
                      tick={{ fill: "#526b7d", fontSize: 11 }}
                    />
                    <Tooltip
                      cursor={{ fill: "#edf7f2" }}
                      formatter={(value) => [formatCurrency(Number(value)), "Facturación"]}
                    />
                    <Bar dataKey="revenue" fill="#00734d" radius={[0, 2, 2, 0]}>
                      <LabelList
                        dataKey="revenue"
                        position="right"
                        formatter={(value) => formatCurrency(Number(value))}
                        fill="#29475e"
                        fontSize={11}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p>Sin ventas registradas.</p>
            )}
          </article>
          <article className="panel advisors">
            <h2>Ranking de asesores</h2>
            {metrics?.advisor_ranking.length ? (
              <>
                <div className="ranking-table-header" aria-hidden="true">
                  <span className="ranking-revenue-head">
                    <span>Regular</span>
                    <span>Recompra</span>
                    <span>Total</span>
                  </span>
                </div>
                <ol className="advisor-ranking">
                  {metrics.advisor_ranking.slice(0, 5).map((advisor, index) => (
                    <li key={advisor.advisor_id}>
                      <span className="ranking-position">{index + 1}</span>
                      <span
                        className={`profile-initials advisor-avatar advisor-avatar-${advisorAvatarTone(advisor.advisor_name)}`}
                        aria-hidden="true"
                      >
                        {advisorInitials(advisor.advisor_name)}
                      </span>
                      <span className="ranking-advisor">
                        <b>{advisor.advisor_name}</b>
                        <small>
                          {advisor.confirmed_repurchases} recompras · {advisor.managed_alerts}{" "}
                          alertas gestionadas
                        </small>
                      </span>
                      <span className="ranking-revenue">
                        <b>{formatCurrency(advisor.regular_revenue)}</b>
                        <b>{formatCurrency(advisor.repurchase_revenue)}</b>
                        <b>{formatCurrency(advisor.total_revenue)}</b>
                      </span>
                    </li>
                  ))}
                </ol>
              </>
            ) : (
              <p>No hay actividad de asesores en el periodo.</p>
            )}
          </article>
          <article className="panel revenue-comparison-panel">
            <h2>Ingresos: ventas regulares vs recompras</h2>
            {metrics ? (
              <div className="product-chart">
                <ResponsiveContainer width="100%" height={360}>
                  <PieChart>
                    <Pie
                      data={[
                        { name: "Ventas regulares", amount: Number(metrics.regular_revenue) },
                        { name: "Recompras", amount: Number(metrics.repurchase_revenue) },
                      ]}
                      dataKey="amount"
                      nameKey="name"
                      cx="50%"
                      cy="45%"
                      innerRadius={76}
                      outerRadius={118}
                      paddingAngle={3}
                    >
                      <Cell fill="#005a9c" />
                      <Cell fill="#00734d" />
                    </Pie>
                    <Tooltip formatter={(value) => [formatCurrency(Number(value)), "Ingresos"]} />
                    <Legend
                      verticalAlign="bottom"
                      iconType="circle"
                      formatter={(value) => <span className="pie-legend">{value}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p>Sin ventas registradas.</p>
            )}
          </article>
        </section>
      )}
      {user.role === "ASESOR" ? (
        <>
          <section className="stats advisor-alert-stats">
            <StatCard label="Para hoy" value={alertSummary.due_today} accent="orange" />
            <StatCard label="Sin gestión" value={alertSummary.unmanaged} accent="purple" />
            <StatCard label="Fuera de fecha" value={alertSummary.overdue} accent="green" />
            <StatCard label="Recompras del mes" value={advisorMetrics?.repurchase_sales ?? "-"} />
          </section>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Mis alertas</h2>
                <p>Selecciona una alerta para revisar el cliente y registrar la gestión.</p>
              </div>
              <span className="header-metric">
                <b>{alertPage.total}</b> activas
              </span>
            </div>
            <form
              className="alert-inbox-filters"
              onSubmit={(event) => {
                event.preventDefault();
                setAlertError("");
                loadAlerts(1).catch(() => setAlertError("No fue posible actualizar las alertas."));
              }}
            >
              <label>
                Buscar
                <input
                  placeholder="Cliente, DNI o teléfono"
                  value={alertFilters.q}
                  onChange={(event) =>
                    setAlertFilters((value) => ({ ...value, q: event.target.value }))
                  }
                />
              </label>
              <label>
                Estado
                <select
                  value={alertFilters.status}
                  onChange={(event) =>
                    setAlertFilters((value) => ({ ...value, status: event.target.value }))
                  }
                >
                  <option value="">Todos</option>
                  <option value="PENDIENTE">Pendiente</option>
                  <option value="REASIGNADO">Reasignada</option>
                  <option value="REPROGRAMADO">Reprogramada</option>
                  <option value="SIN_RESPUESTA">Sin respuesta</option>
                </select>
              </label>
              <label>
                Prioridad
                <select
                  value={alertFilters.priority}
                  onChange={(event) =>
                    setAlertFilters((value) => ({ ...value, priority: event.target.value }))
                  }
                >
                  <option value="">Todas</option>
                  <option value="VENCIDA">Fuera de fecha</option>
                  <option value="HOY">Para hoy</option>
                  <option value="PROXIMA">Próximas</option>
                  <option value="SIN_GESTION">Sin gestión</option>
                </select>
              </label>
              <button>Filtrar alertas</button>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  const reset = { q: "", status: "", priority: "" };
                  setAlertFilters(reset);
                  loadAlerts(1, reset).catch(() =>
                    setAlertError("No fue posible actualizar las alertas."),
                  );
                }}
              >
                Limpiar
              </button>
            </form>
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
                  </tr>
                </thead>
                {Array.from(alertsByCustomer.values()).map((customerAlerts) => {
                  const customer = customerAlerts[0];
                  return (
                    <tbody
                      className="alert-register-customer"
                      key={customer.customer_id || customer.id}
                    >
                      {customerAlerts.map((alert, index) => {
                        const latest = latestAlertAttempt(alert);
                        return (
                          <tr
                            key={alert.id}
                            className="alert-table-row is-actionable"
                            role="button"
                            tabIndex={0}
                            aria-label={`Gestionar alerta de ${alert.product_name || "producto"}`}
                            onClick={() => openAlert(alert)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                openAlert(alert);
                              }
                            }}
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
                              {formatAlertDate(alert.expected_repurchase_date)}
                              <span className="table-detail">
                                Alerta: {formatAlertDate(alert.alert_date)}
                              </span>
                              {daysOverdue(alert.alert_date) > 0 && (
                                <span className="table-detail danger-text">
                                  Atención vencida: {daysOverdue(alert.alert_date)} días
                                </span>
                              )}
                            </td>
                            <td>
                              <span className={alertStatusClass(alert.status)}>
                                {alert.status.replaceAll("_", " ")}
                              </span>
                              <span className="table-detail">
                                {alert.next_action_date
                                  ? `Próxima: ${formatAlertDate(alert.next_action_date)}`
                                  : "Sin próxima acción"}
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
                                    {formatAlertDate(latest.contacted_at, true)}
                                  </span>
                                </>
                              ) : (
                                "Sin gestión"
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  );
                })}
                {!alerts.length && (
                  <tbody>
                    <tr>
                      <td colSpan={6}>No hay alertas activas.</td>
                    </tr>
                  </tbody>
                )}
              </table>
              {alertError && <p className="form-error">{alertError}</p>}
            </div>
            <Pagination
              data={alertPage}
              onPageChange={(page) => loadAlerts(page).catch(() => {})}
            />
          </section>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Próximas alertas</h2>
                <p>Recordatorios informativos; se habilitan para gestión en su fecha.</p>
              </div>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Cliente</th>
                    <th>Producto</th>
                    <th>Tipo</th>
                    <th>Vencimiento</th>
                  </tr>
                </thead>
                <tbody>
                  {upcomingAlerts.map((alert) => (
                    <tr key={`${alert.sale_item_id}-${alert.alert_date}`}>
                      <td>{alert.alert_date}</td>
                      <td>
                        {alert.customer_name}
                        <span className="table-detail">{alert.customer_dni || ""}</span>
                      </td>
                      <td>
                        {alert.product_name}
                        <span className="table-detail">{alert.product_code}</span>
                      </td>
                      <td>
                        <span
                          className={
                            alert.alert_kind === "VENCIMIENTO"
                              ? "status alert-status-pendiente"
                              : "status alert-status-reprogramado"
                          }
                        >
                          {alert.alert_kind === "VENCIMIENTO" ? "Vencimiento" : "Seguimiento"}
                        </span>
                      </td>
                      <td>{alert.expected_repurchase_date}</td>
                    </tr>
                  ))}
                  {!upcomingAlerts.length && (
                    <tr>
                      <td colSpan={5}>No hay próximas alertas configuradas.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : (
        <>
          <section className="panel filters">
            <div className="panel-heading">
              <div>
                <h2>Filtros de alertas</h2>
                <p>Filtra la bandeja de alertas activas del equipo.</p>
              </div>
              <button
                className="secondary"
                onClick={() => {
                  const reset = { q: "", status: "", priority: "" };
                  setAlertFilters(reset);
                  loadAlerts(1, reset).catch(() =>
                    setAlertError("No fue posible actualizar las alertas."),
                  );
                }}
              >
                Limpiar
              </button>
            </div>
            <form
              className="alert-inbox-filters"
              onSubmit={(event) => {
                event.preventDefault();
                setAlertError("");
                loadAlerts(1).catch(() => setAlertError("No fue posible actualizar las alertas."));
              }}
            >
              <label>
                Buscar
                <input
                  placeholder="Cliente, DNI o teléfono"
                  value={alertFilters.q}
                  onChange={(event) =>
                    setAlertFilters((value) => ({ ...value, q: event.target.value }))
                  }
                />
              </label>
              <label>
                Estado
                <select
                  value={alertFilters.status}
                  onChange={(event) =>
                    setAlertFilters((value) => ({ ...value, status: event.target.value }))
                  }
                >
                  <option value="">Todos</option>
                  <option value="PENDIENTE">Pendiente</option>
                  <option value="REASIGNADO">Reasignada</option>
                  <option value="REPROGRAMADO">Reprogramada</option>
                  <option value="SIN_RESPUESTA">Sin respuesta</option>
                </select>
              </label>
              <label>
                Prioridad
                <select
                  value={alertFilters.priority}
                  onChange={(event) =>
                    setAlertFilters((value) => ({ ...value, priority: event.target.value }))
                  }
                >
                  <option value="">Todas</option>
                  <option value="VENCIDA">Fuera de fecha</option>
                  <option value="HOY">Para hoy</option>
                  <option value="PROXIMA">Próximas</option>
                  <option value="SIN_GESTION">Sin gestión</option>
                </select>
              </label>
              <button>Filtrar alertas</button>
            </form>
          </section>
          <section className="panel">
            <h2>Próximos vencimientos</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Cliente / producto</th>
                    <th>Estado</th>
                    <th>Intentos</th>
                    <th>Asignado</th>
                    <th>Desde venta</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.slice(0, 7).map((a) => (
                    <tr key={a.id}>
                      <td>{a.expected_repurchase_date}</td>
                      <td>
                        <b>
                          {[a.customer_first_names, a.customer_last_names]
                            .filter(Boolean)
                            .join(" ") || "Sin cliente"}
                        </b>
                        <span className="table-detail">
                          {a.product_name || a.product_code || "Sin producto"}
                        </span>
                      </td>
                      <td>
                        <span className={alertStatusClass(a.status)}>
                          {a.status.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td>{a.attempts_count}</td>
                      <td>{a.assigned_advisor_name || "Sin asignar"}</td>
                      <td>{daysSince(a.original_sale_date)} días</td>
                    </tr>
                  ))}
                  {!alerts.length && (
                    <tr>
                      <td colSpan={6}>No hay alertas activas.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <Pagination
              data={alertPage}
              onPageChange={(page) => loadAlerts(page).catch(() => {})}
            />
          </section>
        </>
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
              <b>Enfermedad o condición:</b> {selectedAlert.customer_condition || "Sin información"}
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
                {repurchaseSelection === "OTHER" && (
                  <p className="repurchase-info-banner repurchase-recovery-note">
                    La alerta del producto original quedará en recuperación para seguimiento
                    posterior.
                  </p>
                )}
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
                            { product_id: "", quantity: 1 },
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
                          <SearchSelect
                            value={line.product_id}
                            placeholder="Busca por nombre o código"
                            required
                            onChange={(product_id) =>
                              setExtraRepurchaseLines((lines) =>
                                lines.map((item, lineIndex) =>
                                  lineIndex === index ? { ...item, product_id } : item,
                                ),
                              )
                            }
                            options={products
                              .filter(
                                (product) =>
                                  product.id !== selectedAlert.product_id &&
                                  !extraRepurchaseLines.some(
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
                <label className="notes">
                  Enfermedad o condición del cliente
                  <textarea
                    name="customer_condition"
                    defaultValue={selectedAlert.customer_condition || ""}
                    maxLength={500}
                    placeholder="Actualiza solo si hubo cambios"
                  />
                </label>
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
});
