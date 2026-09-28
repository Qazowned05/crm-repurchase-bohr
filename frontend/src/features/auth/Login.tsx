import { useState } from "react";
import { api, setToken } from "../../services/api";
import type { User } from "../../services/types";
export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [error, setError] = useState("");
  return (
    <main className="login">
      <section>
        <p className="eyebrow">CRM FIDELIZACION</p>
        <h1>
          RECOMPRA
          <br />
          BOHR
        </h1>
        <p>Gestión simple de seguimiento, recuperación y recompra.</p>
      </section>
      <form
        className="login-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setError("");
          try {
            const data = Object.fromEntries(new FormData(e.currentTarget));
            const result = await api<{ access_token: string }>("/auth/login", {
              method: "POST",
              body: JSON.stringify(data),
            });
            setToken(result.access_token);
            onLogin(await api<User>("/auth/me"));
          } catch (err) {
            setError(err instanceof Error ? err.message : "Error al ingresar");
          }
        }}
      >
        <h2>Ingresar</h2>
        <label>
          Correo
          <input name="email" type="email" required />
        </label>
        <label>
          Contraseña
          <input name="password" type="password" minLength={8} required />
        </label>
        {error && <p className="error">{error}</p>}
        <button>Iniciar sesión</button>
      </form>
    </main>
  );
}
