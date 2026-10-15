import { useState } from "react";
import { api, setToken } from "../../services/api";
import type { User } from "../../services/types";
export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  return (
    <main className="login">
      <section className="login-card">
        <header className="login-brand">
          <img src="/bohr-flow-sin-fondo-ajustado.png" alt="BOHR Flow" />
        </header>
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
          <div className="login-heading">
            <h1>Iniciar sesión</h1>
            <p>Accede al sistema de gestión de recompra.</p>
          </div>
          <label>
            Correo
            <input name="email" type="email" autoComplete="email" required autoFocus />
          </label>
          <label>
            Contraseña
            <span className="login-password-field">
              <input
                name="password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                minLength={8}
                required
              />
              <button
                type="button"
                className="password-visibility"
                onClick={() => setShowPassword((visible) => !visible)}
                aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                title={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  {showPassword ? (
                    <>
                      <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
                      <circle cx="12" cy="12" r="2.8" />
                    </>
                  ) : (
                    <>
                      <path d="M4 4l16 16" />
                      <path d="M6.2 6.3C4 7.9 2.5 10.2 2.5 12c0 0 3.5 6 9.5 6 1.7 0 3.2-.5 4.5-1.2" />
                      <path d="M9.3 6.2A10.6 10.6 0 0 1 12 6c6 0 9.5 6 9.5 6a14.6 14.6 0 0 1-2.9 3.6" />
                    </>
                  )}
                </svg>
              </button>
            </span>
          </label>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <button type="submit">Iniciar sesión</button>
        </form>
      </section>
    </main>
  );
}
