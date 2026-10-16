import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { clearToken, api } from "../services/api";
import type { User } from "../services/types";
import { Login } from "../features/auth/Login";
import { Dashboard } from "../features/dashboard/Dashboard";
import { RecoveryQueue } from "../features/recovery/RecoveryQueue";
import { Maintenance } from "../features/maintenance/Maintenance";
import { Configuration } from "../features/configuration/Configuration";
import { Sales } from "../features/sales/Sales";
import { AlertRegister } from "../features/alerts/AlertRegister";
import { Operations } from "../features/operations/Operations";
type View =
  | "dashboard"
  | "sales"
  | "alert-register"
  | "recovery"
  | "customers"
  | "products"
  | "users"
  | "configuration"
  | "operations";

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
  if (view === "alert-register")
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" {...common}>
        <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
        <path d="M10 21h4" />
      </svg>
    );
  if (view === "recovery")
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
  const [openNavGroups, setOpenNavGroups] = useState<Record<string, boolean>>({
    Principal: true,
    Operación: true,
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
  const viewLabels: Record<View, string> = {
    dashboard: "Resumen",
    sales: "Ventas",
    "alert-register": "Alertas",
    recovery: "Recuperación",
    customers: "Clientes",
    products: "Productos y reglas",
    users: "Usuarios",
    configuration: "Tipificaciones",
    operations: "Operaciones",
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
  };
  const pathToView = Object.fromEntries(
    Object.entries(viewPaths).map(([viewId, path]) => [path, viewId]),
  ) as Record<string, View>;
  const view = pathToView[location.pathname];
  if (!view) return <Navigate to="/" replace />;
  const navGroups: Array<{ label: string; items: Array<[View, string]> }> = [
    { label: "Principal", items: [["dashboard", "Resumen"]] },
    {
      label: "Operación",
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
  ];
  if (supervisor) {
    navGroups.push({
      label: "Administración",
      items: [
        ["customers", "Clientes"],
        ["products", "Productos"],
        ["configuration", "Tipificaciones"],
        ...(user.role === "ADMIN" ? [["users", "Usuarios"] as [View, string]] : []),
      ],
    });
  }
  const renderView = (activeView: View) =>
    activeView === "dashboard" ? (
      <Dashboard user={user} />
    ) : activeView === "sales" ? (
      <Sales user={user} />
    ) : activeView === "alert-register" ? (
      <AlertRegister />
    ) : activeView === "recovery" ? (
      supervisor ? (
        <RecoveryQueue />
      ) : (
        <Dashboard user={user} />
      )
    ) : activeView === "configuration" ? (
      <Configuration />
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
    ["recovery", "customers", "products", "configuration", "operations", "users"].includes(view)
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
              {profileMenuOpen ? "-" : "+"}
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
        <section key={view}>{renderView(view)}</section>
      </main>
    </div>
  );
}
