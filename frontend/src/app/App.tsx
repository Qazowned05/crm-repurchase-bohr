import { useEffect, useState } from "react";
import { clearToken, api } from "../services/api";
import type { User } from "../services/types";
import { Login } from "../features/auth/Login";
import { Dashboard } from "../features/dashboard/Dashboard";
import { RecoveryQueue } from "../features/recovery/RecoveryQueue";
import { Maintenance } from "../features/maintenance/Maintenance";
import { Configuration } from "../features/configuration/Configuration";
import { Sales } from "../features/sales/Sales";
type View =
  "dashboard" | "sales" | "recovery" | "customers" | "products" | "users" | "configuration";
export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [view, setView] = useState<View>("dashboard");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(clearToken)
      .finally(() => setReady(true));
  }, []);
  if (!ready) return <main className="loading">Cargando CRM...</main>;
  if (!user) return <Login onLogin={setUser} />;
  const supervisor = user.role !== "ASESOR";
  const nav: Array<[View, string]> = [
    ["dashboard", "Resumen"],
    ["sales", "Registrar venta"],
  ];
  if (supervisor)
    nav.push(
      ["recovery", "Recuperación"],
      ["customers", "Clientes"],
      ["products", "Productos"],
      ["configuration", "Tipificaciones"],
    );
  if (user.role === "ADMIN") nav.push(["users", "Usuarios"]);
  const content =
    view === "dashboard" ? (
      <Dashboard user={user} />
    ) : view === "sales" ? (
      <Sales />
    ) : view === "recovery" ? (
      <RecoveryQueue />
    ) : view === "configuration" ? (
      <Configuration />
    ) : (
      <Maintenance kind={view} user={user} />
    );
  return (
    <div className="shell">
      <aside>
        <div className="brand">
          <span>RB</span>
          <b>
            RECOMPRA
            <br />
            BOHR
          </b>
        </div>
        <nav>
          {nav.map(([id, label]) => (
            <button key={id} className={view === id ? "active" : ""} onClick={() => setView(id)}>
              {label}
            </button>
          ))}
        </nav>
        <div className="profile">
          <b>{user.full_name}</b>
          <small>{user.role}</small>
          <button
            onClick={() => {
              clearToken();
              setUser(null);
            }}
          >
            Cerrar sesión
          </button>
        </div>
      </aside>
      <main className="content">{content}</main>
    </div>
  );
}
