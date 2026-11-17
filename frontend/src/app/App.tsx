import { useCallback, useEffect, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { clearToken, api } from "../services/api";
import type { AlertNotification, LeadNotification, User } from "../services/types";
import { Login } from "../features/auth/Login";
import { Dashboard } from "../features/dashboard/Dashboard";
import { RecoveryQueue } from "../features/recovery/RecoveryQueue";
import { Maintenance } from "../features/maintenance/Maintenance";
import { Configuration } from "../features/configuration/Configuration";
import { Sales } from "../features/sales/Sales";
import { AlertRegister } from "../features/alerts/AlertRegister";
import { Operations } from "../features/operations/Operations";
import { Leads } from "../features/leads/Leads";
import { LeadsDashboard } from "../features/leads/LeadsDashboard";
import { LeadRecoveryQueue } from "../features/leads/LeadRecoveryQueue";
import { Campaigns } from "../features/campaigns/Campaigns";
type View =
  | "dashboard"
  | "sales"
  | "alert-register"
  | "recovery"
  | "customers"
  | "products"
  | "users"
  | "configuration"
  | "operations"
  | "leads"
  | "leads-dashboard"
  | "lead-recovery"
  | "campaigns";
type NotificationItem =
  | { kind: "ALERT"; value: AlertNotification }
  | { kind: "LEAD"; value: LeadNotification };

function notificationDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function NavIcon({ view }: { view: View }) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.8 };
  if (view === "dashboard")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <rect x="3" y="3" width="7" height="7" />
        <rect x="14" y="3" width="7" height="7" />
        <rect x="3" y="14" width="7" height="7" />
        <rect x="14" y="14" width="7" height="7" />
      </svg>
    );
  if (view === "sales")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <path d="M4 19V5m0 14h16" />
        <path d="m7 15 4-4 3 2 5-6" />
      </svg>
    );
  if (view === "leads")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20c0-3.2 2.7-5.5 6-5.5s6 2.3 6 5.5" />
        <path d="M17 9h4M19 7v4" />
      </svg>
    );
  if (view === "alert-register")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
        <path d="M10 21h4" />
      </svg>
    );
  if (view === "recovery" || view === "lead-recovery")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <path d="M20 11a8 8 0 1 0 2 5" />
        <path d="M20 4v7h-7" />
      </svg>
    );
  if (view === "operations")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <path d="M12 3v12" />
        <path d="m7 8 5-5 5 5" />
        <path d="M5 14v6h14v-6" />
      </svg>
    );
  if (view === "customers")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20c0-3.2 2.7-5.5 6-5.5s6 2.3 6 5.5" />
        <path d="M17 7a3 3 0 0 1 0 5.8M18 15c2 .5 3 2.2 3 5" />
      </svg>
    );
  if (view === "products")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <path d="m4 7 8-4 8 4-8 4-8-4Z" />
        <path d="v10l8 4 8-4V7M12 11v9" />
      </svg>
    );
  if (view === "configuration")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.1 2.1-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2h-3v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1-2.1-2.1.1-.1A1.7 1.7 0 0 0 7 15a1.7 1.7 0 0 0-1.5-1H5.3v-3h.2A1.7 1.7 0 0 0 7 10a1.7 1.7 0 0 0-.3-1.9l-.1-.1 2.1-2.1.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5v-.2h3v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1 2.1 2.1-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2v3h-.2a1.7 1.7 0 0 0-1.4 1Z" />
      </svg>
    );
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21c0-4 3.6-6.5 8-6.5s8 2.5 8 6.5" />
    </svg>
  );
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [closedAlertReminderIds, setClosedAlertReminderIds] = useState<Set<string>>(new Set());
  const [alertToManageId, setAlertToManageId] = useState<string | null>(null);
  const [leadToManageId, setLeadToManageId] = useState<string | null>(null);
  const notificationsMenuRef = useRef<HTMLDivElement>(null);
  const [openNavGroups, setOpenNavGroups] = useState<Record<string, boolean>>({
    Principal: true,
    Recompra: true,
    Seguimiento: true,
    Administración: true,
  });
  const location = useLocation();
  const routerNavigate = useNavigate();
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(clearToken)
      .finally(() => setReady(true));
  }, []);
  useEffect(() => {
    if (!user) return;
    const loadNotifications = () => Promise.all([
      api<AlertNotification[]>("/alerts/notifications"),
      api<LeadNotification[]>("/leads/notifications"),
    ]).then(([alerts, leads]) => setNotifications([
      ...alerts.map((value) => ({ kind: "ALERT" as const, value })),
      ...leads.map((value) => ({ kind: "LEAD" as const, value })),
    ])).catch(() => {});
    void loadNotifications();
    const timer = window.setInterval(() => void loadNotifications(), 10_000);
    return () => window.clearInterval(timer);
  }, [user?.id]);
  useEffect(() => setClosedAlertReminderIds(new Set()), [user?.id]);
  useEffect(() => {
    if (!notificationsOpen) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!notificationsMenuRef.current?.contains(event.target as Node)) setNotificationsOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [notificationsOpen]);
  const handleAlertOpened = useCallback(() => setAlertToManageId(null), []);
  const handleLeadOpened = useCallback(() => setLeadToManageId(null), []);
  if (!ready) return <main className="loading">Cargando CRM...</main>;
  if (!user)
    return (
      <Login
        onLogin={(nextUser) => {
          setUser(nextUser);
          routerNavigate("/", { replace: true });
        }}
      />
    );
  const supervisor = user.role !== "ASESOR";
  const alertReminders = user.role === "ASESOR"
    ? notifications.filter((notification): notification is Extract<NotificationItem, { kind: "ALERT" }> =>
      notification.kind === "ALERT" && !closedAlertReminderIds.has(notification.value.id))
    : [];
  const currentAlertReminder = alertReminders[0];
  const viewLabels: Record<View, string> = {
    dashboard: "Resumen",
    sales: "Ventas",
    "alert-register": "Alertas",
    recovery: "Recuperación",
    customers: "Clientes",
    products: "Productos y reglas",
    users: "Usuarios",
    configuration: "Tipificaciones",
    campaigns: "Campañas",
    operations: "Operaciones",
    leads: "Leads",
    "leads-dashboard": "Resumen de Leads",
    "lead-recovery": "Leads recuperables",
  };
  const viewPaths: Record<View, string> = {
    dashboard: "/",
    sales: "/ventas",
    "alert-register": "/alertas",
    recovery: "/recuperacion",
    customers: "/clientes",
    products: "/productos",
    users: "/usuarios",
    configuration: "/tipificaciones",
    operations: "/operaciones",
    leads: "/leads",
    "leads-dashboard": "/leads/resumen",
    "lead-recovery": "/leads-recuperables",
    campaigns: "/campanas",
  };
  const pathToView = Object.fromEntries(
    Object.entries(viewPaths).map(([viewId, path]) => [path, viewId]),
  ) as Record<string, View>;
  const view = pathToView[location.pathname];
  if (!view) return <Navigate to="/" replace />;
  const navGroups: Array<{ label: string; items: Array<[View, string]> }> = [
    { label: "Principal", items: [["dashboard", "Resumen"]] },
    {
      label: "Recompra",
      items: [
        ["sales", "Ventas"],
        ["alert-register", "Registro de alertas"],
        ...(supervisor
          ? [
              ["recovery", "Recuperación"],
              ["operations", "Importaciones y reportes"],
            ]
          : []),
      ] as Array<[View, string]>,
    },
    {
      label: "Seguimiento",
      items: [
        ["leads", "Leads"],
        ...(supervisor ? [["leads-dashboard", "Resumen de Leads"] as [View, string], ["lead-recovery", "Leads recuperables"] as [View, string]] : []),
      ],
    },
  ];
  if (supervisor) {
    navGroups.push({
      label: "Administración",
      items: [
        ["customers", "Clientes"],
        ["products", "Productos"],
        ["configuration", "Tipificaciones"],
        ["campaigns", "Campañas"],
        ...(user.role === "ADMIN" ? [["users", "Usuarios"] as [View, string]] : []),
      ],
    });
  }
  const renderView = (activeView: View) =>
    activeView === "dashboard" ? (
      <Dashboard user={user} alertToManageId={alertToManageId} onAlertOpened={handleAlertOpened} />
    ) : activeView === "sales" ? (
      <Sales user={user} />
    ) : activeView === "leads" ? (
      <Leads user={user} leadToManageId={leadToManageId} onLeadOpened={handleLeadOpened} />
    ) : activeView === "leads-dashboard" ? (
      supervisor ? <LeadsDashboard /> : <Dashboard user={user} />
    ) : activeView === "lead-recovery" ? (
      supervisor ? <LeadRecoveryQueue /> : <Dashboard user={user} />
    ) : activeView === "alert-register" ? (
      <AlertRegister user={user} />
    ) : activeView === "recovery" ? (
      supervisor ? (
        <RecoveryQueue />
      ) : (
        <Dashboard user={user} />
      )
    ) : activeView === "configuration" ? (
      <Configuration />
    ) : activeView === "campaigns" ? (
      <Campaigns />
    ) : activeView === "operations" ? (
      <Operations />
    ) : (
      <Maintenance kind={activeView} user={user} />
    );
  const navigate = (nextView: View) => {
    routerNavigate(viewPaths[nextView]);
  };
  if (
    !supervisor &&
    ["recovery", "lead-recovery", "customers", "products", "configuration", "campaigns", "operations", "users"].includes(view)
  )
    return <Navigate to="/" replace />;
  if (user.role !== "ADMIN" && view === "users") return <Navigate to="/" replace />;
  return (
    <div className={`shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <aside className="app-sidebar">
        <div className="sidebar-top">
          <div className="brand">
            <img src="/bohr-flow-sin-fondo-ajustado.png" alt="BOHR Flow" />
          </div>
        </div>
        <nav>
          {navGroups.map((group) => (
            <section className="nav-group" key={group.label} aria-label={group.label}>
              <button
                className="nav-group-toggle"
                type="button"
                onClick={() =>
                  setOpenNavGroups((groups) => ({ ...groups, [group.label]: !groups[group.label] }))
                }
                aria-expanded={openNavGroups[group.label]}
              >
                <span>{group.label}</span>
                <span className="nav-disclosure" aria-hidden="true">
                  {openNavGroups[group.label] ? "-" : "+"}
                </span>
              </button>
              {openNavGroups[group.label] && (
                <div className="nav-group-items">
                  {group.items.map(([id, label]) => (
                    <button
                      key={id}
                      className={view === id ? "active" : ""}
                      onClick={() => navigate(id)}
                    >
                      <NavIcon view={id} />
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          ))}
        </nav>
        <div className="profile-card">
          <button
            className="profile-trigger"
            type="button"
            onClick={() => setProfileMenuOpen((open) => !open)}
            aria-expanded={profileMenuOpen}
            aria-label="Abrir opciones de usuario"
          >
            <span className="profile-initials" aria-hidden="true">
              {user.full_name
                .split(" ")
                .slice(0, 2)
                .map((part) => part[0])
                .join("")}
            </span>
            <span className="profile-details">
              <b>{user.full_name}</b>
              <small>{user.role}</small>
            </span>
            <span className="profile-disclosure" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="m7 10 5 5 5-5" />
              </svg>
            </span>
          </button>
          {profileMenuOpen && (
            <div className="profile-menu">
              <button
                type="button"
                onClick={() => {
                  clearToken();
                  setUser(null);
                  routerNavigate("/", { replace: true });
                }}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M10 5H5v14h5" />
                  <path d="m14 8 4 4-4 4M18 12H9" />
                </svg>
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </aside>
      <main className="content">
        <header className="app-header">
          <div className="app-header-title">
            <p>CRM RECOMPRA</p>
            <h1>{viewLabels[view]}</h1>
          </div>
          <div className="app-header-actions">
            <span className="app-role">{user.role}</span>
            <div className="notifications-menu" ref={notificationsMenuRef}>
              <button
                type="button"
                className="notifications-trigger"
                onClick={() => setNotificationsOpen((open) => !open)}
                aria-label="Abrir notificaciones"
                aria-expanded={notificationsOpen}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
                  <path d="M10 21h4" />
                </svg>
                {notifications.length > 0 && <span>{notifications.length}</span>}
              </button>
              {notificationsOpen && (
                <section className="notifications-panel" aria-label="Notificaciones">
                  <header>
                    <div>
                      <p>RECORDATORIOS</p>
                      <strong>Notificaciones</strong>
                    </div>
                    <small>{notifications.length ? `${notifications.length} pendientes` : "Sin pendientes"}</small>
                  </header>
                  {notifications.map((notification) => (
                    <article key={`${notification.kind}-${notification.value.id}`}>
                      <span className="notification-mark" aria-hidden="true">
                        <svg viewBox="0 0 24 24">
                          <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
                          <path d="M10 21h4" />
                        </svg>
                      </span>
                      <button
                        type="button"
                        className="notification-entry"
                        onClick={() => {
                          setNotificationsOpen(false);
                          if (notification.kind === "ALERT") {
                            setAlertToManageId(notification.value.alert_id);
                            routerNavigate("/");
                          } else {
                            setLeadToManageId(notification.value.lead_id);
                            routerNavigate("/leads");
                          }
                        }}
                      >
                        <b>Acción programada</b>
                        <span>
                          {notification.kind === "LEAD"
                            ? user.role === "ASESOR"
                              ? `Gestiona el lead de ${notification.value.lead.full_name}.`
                              : `Lead asignado a ${notification.value.lead.assigned_advisor_name || "asesor sin asignar"}: ${notification.value.lead.full_name}.`
                            : user.role === "ASESOR"
                              ? `Gestiona la alerta de ${notification.value.alert.customer_first_names || "este cliente"}.`
                              : `Asignada a ${notification.value.alert.assigned_advisor_name || "asesor sin asignar"}: ${notification.value.alert.customer_first_names || "cliente sin nombre"}.`}
                        </span>
                      </button>
                      <button
                        type="button"
                        className="notification-dismiss"
                        aria-label="Eliminar notificación"
                        onClick={() => {
                          api<void>(notification.kind === "LEAD" ? `/leads/notifications/${notification.value.id}` : `/alerts/notifications/${notification.value.id}`, { method: "DELETE" })
                            .then(() => setNotifications((items) => items.filter((item) => item.value.id !== notification.value.id || item.kind !== notification.kind)))
                            .catch(() => {});
                        }}
                      >
                        ×
                      </button>
                    </article>
                  ))}
                </section>
              )}
            </div>
            <button
              type="button"
              className="sidebar-toggle"
              onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
              aria-label={sidebarCollapsed ? "Mostrar navegación" : "Ocultar navegación"}
            >
              {sidebarCollapsed ? "Mostrar navegación" : "Ocultar navegación"}
            </button>
          </div>
        </header>
        {currentAlertReminder && (
          <div className="scheduled-alert-reminders" role="alert" aria-label="Agendamientos pendientes">
            <article>
              <div>
                <p>{alertReminders.length} AGENDAMIENTO{alertReminders.length === 1 ? "" : "S"} PENDIENTE{alertReminders.length === 1 ? "" : "S"}</p>
                <strong>{currentAlertReminder.value.alert.customer_first_names || "Cliente sin nombre"}</strong>
                <span>Próximo: {notificationDate(currentAlertReminder.value.scheduled_for)}</span>
              </div>
              <button
                type="button"
                className="scheduled-alert-open"
                onClick={() => {
                  setAlertToManageId(currentAlertReminder.value.alert_id);
                  routerNavigate("/");
                }}
              >
                Gestionar
              </button>
              <button
                type="button"
                className="scheduled-alert-close"
                aria-label="Cerrar aviso de agendamientos"
                onClick={() => setClosedAlertReminderIds(new Set(alertReminders.map((notification) => notification.value.id)))}
              >
                Cerrar
              </button>
            </article>
          </div>
        )}
        <section key={view}>{renderView(view)}</section>
      </main>
    </div>
  );
}
