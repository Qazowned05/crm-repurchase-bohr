import { useEffect, useState } from "react";
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
export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [ready, setReady] = useState(false);
  const [visitedViews, setVisitedViews] = useState<Set<View>>(() => new Set(["dashboard"]));
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [openNavGroups, setOpenNavGroups] = useState<Record<string, boolean>>({
    Principal: false,
    Operación: false,
    Administración: false,
  });
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
          setView("dashboard");
          setVisitedViews(new Set(["dashboard"]));
        }}
      />
    );
  const supervisor = user.role !== "ASESOR";
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
    setVisitedViews((views) => new Set(views).add(nextView));
    setView(nextView);
  };
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
                      {label}
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
                  setView("dashboard");
                  setVisitedViews(new Set(["dashboard"]));
                }}
              >
                Cerrar sesión
              </button>
            </div>
          )}
        </div>
      </aside>
      <main className="content">
        <div className="content-sidebar-control">
          <button type="button" onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}>
            {sidebarCollapsed ? "Mostrar panel" : "Ocultar panel"}
          </button>
        </div>
        {Array.from(visitedViews).map((visitedView) => (
          <section key={visitedView} hidden={view !== visitedView}>
            {renderView(visitedView)}
          </section>
        ))}
      </main>
    </div>
  );
}
