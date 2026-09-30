import { useEffect, useState } from "react";
import { api, download, listAll, upload } from "../../services/api";
import type { Product, User } from "../../services/types";

type ImportType = "customers" | "products" | "historical_sales";
type ImportResult = {
  id: string;
  state: string;
  total_rows: number;
  valid_rows: number;
  rejected_rows: number;
  errors: Array<{ row_number?: number; message: string }>;
};

export function Operations() {
  const [kind, setKind] = useState<ImportType>("customers");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [advisors, setAdvisors] = useState<User[]>([]);
  const [allowUpdates, setAllowUpdates] = useState(false);
  const [allowReassignment, setAllowReassignment] = useState(false);
  const [filters, setFilters] = useState({
    start_date: "",
    end_date: "",
    product_id: "",
    sale_advisor_id: "",
    portfolio_advisor_id: "",
    assigned_advisor_id: "",
    channel: "",
    purchase_type: "",
    alert_status: "",
  });
  useEffect(() => {
    listAll<Product>("/products")
      .then(setProducts)
      .catch(() => {});
    listAll<User>("/users")
      .then((rows) => setAdvisors(rows.filter((user) => user.role === "ASESOR")))
      .catch(() => {});
  }, []);
  async function preview() {
    if (!file) return;
    setError("");
    setResult(null);
    const form = new FormData();
    form.append("file", file);
    form.append("allow_updates", String(allowUpdates));
    form.append("allow_reassignment", String(allowReassignment));
    try {
      setResult(await upload<ImportResult>(`/imports/${kind}/preview`, form));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible validar el archivo.");
    }
  }
  async function commit() {
    if (!result) return;
    setError("");
    try {
      await api(`/imports/${result.id}/commit`, { method: "POST" });
      setResult(null);
      setFile(null);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "No fue posible completar la importación.",
      );
    }
  }
  async function downloadReport() {
    setError("");
    try {
      await download(
        `/reports/operation.xlsx${query ? `?${query}` : ""}`,
        "reporte_operacion.xlsx",
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible descargar el reporte.");
    }
  }
  async function downloadTemplate() {
    setError("");
    try {
      await download(`/imports/templates/${kind}`, `plantilla_${kind}.xlsx`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible descargar la plantilla.");
    }
  }
  const query = new URLSearchParams(
    Object.entries(filters).filter(([, value]) => value) as Array<[string, string]>,
  ).toString();
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">OPERACIÓN</p>
          <h1>Importaciones y reportes</h1>
        </div>
      </div>
      <section className="panel operations-panel">
        <div className="operation-section-heading">
          <div>
            <h2>Importación masiva</h2>
            <p>Valida el archivo antes de incorporarlo al sistema.</p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            Tipo
            <select
              value={kind}
              onChange={(event) => {
                setKind(event.target.value as ImportType);
                setResult(null);
              }}
            >
              <option value="customers">Clientes</option>
              <option value="products">Productos</option>
              <option value="historical_sales">Ventas históricas</option>
            </select>
          </label>
          <label>
            Archivo Excel
            <input
              type="file"
              accept=".xlsx"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={allowUpdates}
              onChange={(event) => setAllowUpdates(event.target.checked)}
            />
            Permitir actualizar clientes o productos existentes
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={allowReassignment}
              onChange={(event) => setAllowReassignment(event.target.checked)}
            />
            Permitir reasignar el asesor responsable
          </label>
        </div>
        <div className="operation-actions">
          <div>
            <span>1. Prepara el archivo</span>
            <button className="secondary" onClick={downloadTemplate}>
              Descargar plantilla
            </button>
          </div>
          <div>
            <span>2. Revisa antes de importar</span>
            <button disabled={!file} onClick={preview}>
              Validar archivo
            </button>
          </div>
        </div>
        {result && (
          <div className="import-result">
            <p>
              <b>{result.state}</b> · {result.valid_rows} válidas de {result.total_rows} filas ·{" "}
              {result.rejected_rows} rechazadas
            </p>
            {result.errors.map((item, index) => (
              <p className="form-error" key={index}>
                Fila {item.row_number || "general"}: {item.message}
              </p>
            ))}
            {result.state === "PREVIEW_READY" && (
              <button onClick={commit}>Importar {result.valid_rows} filas validadas</button>
            )}
          </div>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
      </section>
      <section className="panel operations-panel">
        <div className="operation-section-heading">
          <div>
            <h2>Reporte de operación</h2>
            <p>Descarga ventas, alertas y gestiones en un único Excel.</p>
          </div>
        </div>
        <div className="form-grid">
          <label>
            Desde
            <input
              type="date"
              value={filters.start_date}
              onChange={(event) =>
                setFilters((value) => ({ ...value, start_date: event.target.value }))
              }
            />
          </label>
          <label>
            Hasta
            <input
              type="date"
              value={filters.end_date}
              onChange={(event) =>
                setFilters((value) => ({ ...value, end_date: event.target.value }))
              }
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
              <option value="">Todos</option>
              {products.map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name} ({product.code})
                </option>
              ))}
            </select>
          </label>
          <label>
            Asesor que vendió
            <select
              value={filters.sale_advisor_id}
              onChange={(event) =>
                setFilters((value) => ({ ...value, sale_advisor_id: event.target.value }))
              }
            >
              <option value="">Todos</option>
              {advisors.map((advisor) => (
                <option key={advisor.id} value={advisor.id}>
                  {advisor.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Responsable de cartera
            <select
              value={filters.portfolio_advisor_id}
              onChange={(event) =>
                setFilters((value) => ({ ...value, portfolio_advisor_id: event.target.value }))
              }
            >
              <option value="">Todos</option>
              {advisors.map((advisor) => (
                <option key={advisor.id} value={advisor.id}>
                  {advisor.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Asesor asignado a alerta
            <select
              value={filters.assigned_advisor_id}
              onChange={(event) =>
                setFilters((value) => ({ ...value, assigned_advisor_id: event.target.value }))
              }
            >
              <option value="">Todos</option>
              {advisors.map((advisor) => (
                <option key={advisor.id} value={advisor.id}>
                  {advisor.full_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Canal
            <select
              value={filters.channel}
              onChange={(event) =>
                setFilters((value) => ({ ...value, channel: event.target.value }))
              }
            >
              <option value="">Todos</option>
              <option value="TV">TV</option>
              <option value="DIGITAL">Digital</option>
              <option value="OTROS">Otros</option>
            </select>
          </label>
          <label>
            Tipo de compra
            <select
              value={filters.purchase_type}
              onChange={(event) =>
                setFilters((value) => ({ ...value, purchase_type: event.target.value }))
              }
            >
              <option value="">Todos</option>
              <option value="COMPRA">Regular</option>
              <option value="RECOMPRA">Recompra</option>
            </select>
          </label>
          <label>
            Estado de alerta
            <select
              value={filters.alert_status}
              onChange={(event) =>
                setFilters((value) => ({ ...value, alert_status: event.target.value }))
              }
            >
              <option value="">Todos</option>
              <option value="PENDIENTE">Pendiente</option>
              <option value="REASIGNADO">Reasignada</option>
              <option value="REPROGRAMADO">Reprogramada</option>
              <option value="SIN_RESPUESTA">Sin respuesta</option>
              <option value="VENCIDO_NO_GESTIONADO">Vencida</option>
              <option value="CERRADO_POR_TIPIFICACION">Cerrada por tipificación</option>
              <option value="RECOMPRA_LOGRADA">Recompra lograda</option>
              <option value="COMPRA_OTRO_PRODUCTO">Compra de otro producto</option>
              <option value="NO_INTERESADO">No interesado</option>
              <option value="CANCELADO_POR_RECOMPRA">Cancelada por recompra</option>
              <option value="CANCELADO_POR_ANULACION">Cancelada por anulación</option>
            </select>
          </label>
        </div>
        <div className="report-action">
          <button onClick={downloadReport}>Descargar reporte Excel</button>
        </div>
      </section>
    </>
  );
}
