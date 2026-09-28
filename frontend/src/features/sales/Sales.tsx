import { useEffect, useState } from "react";
import { CrudModal } from "../../components/CrudModal";
import { Modal } from "../../components/Modal";
import { api } from "../../services/api";
import { StatCard } from "../../components/StatCard";
import type {
  AdvisorSalesMetrics,
  AlertGeneration,
  Customer,
  Product,
  Sale,
  User,
} from "../../services/types";

type SaleLine = { product_id: string; quantity: number };

const customerFields = [
  { name: "dni", label: "DNI", required: true },
  { name: "first_names", label: "Nombres", required: true },
  { name: "last_names", label: "Apellidos", required: true },
  { name: "phone", label: "Teléfono", required: true },
  { name: "email", label: "Correo", type: "email" },
  { name: "condition", label: "Enfermedad o condición" },
  { name: "birth_year", label: "Año de nacimiento", type: "number" },
  { name: "sales_district", label: "Distrito de venta" },
];

export function Sales({ user }: { user: User }) {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [sales, setSales] = useState<Sale[]>([]);
  const [metrics, setMetrics] = useState<AdvisorSalesMetrics | null>(null);
  const [open, setOpen] = useState(false);
  const [customerModal, setCustomerModal] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [lines, setLines] = useState<SaleLine[]>([{ product_id: "", quantity: 1 }]);
  const [channel, setChannel] = useState("TV");
  const [error, setError] = useState("");
  const [generationMessage, setGenerationMessage] = useState("");
  const [generating, setGenerating] = useState(false);
  const advisor = user.role === "ASESOR";
  const load = async () => {
    const [customerRows, productRows, saleRows, advisorMetrics] = await Promise.all([
      api<Customer[]>("/customers"),
      api<Product[]>("/products"),
      api<Sale[]>("/sales"),
      advisor ? api<AdvisorSalesMetrics>("/sales/me/metrics") : Promise.resolve(null),
    ]);
    setCustomers(customerRows);
    setProducts(productRows.filter((product) => product.is_active));
    setSales(saleRows);
    setMetrics(advisorMetrics);
  };
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar el espacio de ventas."));
  }, []);
  const closeSale = () => {
    setOpen(false);
    setError("");
  };
  const saveCustomer = async (data: Record<string, unknown>) => {
    const customer = await api<Customer>("/customers", {
      method: "POST",
      body: JSON.stringify(data),
    });
    setCustomers((rows) =>
      [...rows, customer].sort((a, b) =>
        `${a.last_names} ${a.first_names}`.localeCompare(`${b.last_names} ${b.first_names}`),
      ),
    );
    setCustomerId(customer.id);
    setError("");
  };
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await api("/sales", {
        method: "POST",
        body: JSON.stringify({
          customer_id: customerId,
          sale_date: form.get("sale_date"),
          notes: form.get("notes") || undefined,
          acquisition_channel: channel,
          acquisition_channel_detail:
            channel === "OTROS" ? form.get("acquisition_channel_detail") : undefined,
          items: lines,
        }),
      });
      closeSale();
      setLines([{ product_id: "", quantity: 1 }]);
      load().catch(() =>
        setError("La venta se registró, pero no fue posible actualizar el historial."),
      );
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible registrar la venta.");
    }
  };
  const generateAlerts = async () => {
    setGenerating(true);
    setGenerationMessage("");
    try {
      const result = await api<AlertGeneration>("/alerts/generate", { method: "POST" });
      setGenerationMessage(`Alertas generadas para ${result.run_date}: ${result.created} nuevas.`);
    } catch (reason) {
      setGenerationMessage(
        reason instanceof Error ? reason.message : "No fue posible generar alertas.",
      );
    } finally {
      setGenerating(false);
    }
  };
  const customerName = (customerId: string) => {
    const customer = customers.find((row) => row.id === customerId);
    return customer ? `${customer.last_names} ${customer.first_names}` : customerId;
  };
  const saleProducts = (sale: Sale) =>
    sale.items
      .map((item) => {
        const product = products.find((row) => row.id === item.product_id);
        return `${product ? product.name : item.product_id} x${item.quantity}`;
      })
      .join(", ");
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">VENTAS</p>
          <h1>Ventas</h1>
          <p>
            {advisor
              ? "Registra y consulta tus ventas."
              : "Consulta las ventas registradas por el equipo."}
          </p>
        </div>
        <button
          onClick={() => {
            setError("");
            setOpen(true);
          }}
        >
          Registrar venta
        </button>
      </div>
      {advisor && (
        <section className="stats">
          <StatCard label="Ventas confirmadas" value={metrics?.confirmed_sales ?? "-"} />
          <StatCard
            label="Productos confirmados"
            value={metrics?.confirmed_items ?? "-"}
            accent="green"
          />
          <StatCard label="Recompras" value={metrics?.repurchase_sales ?? "-"} accent="purple" />
          <StatCard
            label="Productos en recompra"
            value={metrics?.repurchase_items ?? "-"}
            accent="orange"
          />
        </section>
      )}
      {!advisor && (
        <section className="panel sales-operations">
          <div className="panel-heading">
            <div>
              <h2>Generación de alertas</h2>
              <p>
                Genera las alertas pendientes hoy. La generación programada se habilitará en una
                próxima operación.
              </p>
            </div>
            <button onClick={generateAlerts} disabled={generating}>
              {generating ? "Generando..." : "Generar alertas"}
            </button>
          </div>
          {generationMessage && (
            <p
              className={
                generationMessage.includes("No fue posible") ? "form-error" : "success-message"
              }
            >
              {generationMessage}
            </p>
          )}
        </section>
      )}
      <section className="panel">
        <h2>{advisor ? "Tu espacio de ventas" : "Registro de ventas"}</h2>
        <p>
          Selecciona un cliente existente o créalo durante el registro. Solo se muestran productos
          activos.
        </p>
      </section>
      <section className="panel sales-history">
        <div className="panel-heading">
          <div>
            <h2>{advisor ? "Mi historial de ventas" : "Historial de ventas"}</h2>
            <p>
              {advisor
                ? "Solo se muestran las ventas que registraste."
                : "Incluye las ventas registradas por todos los asesores."}
            </p>
          </div>
          <span className="header-metric">
            <b>{sales.length}</b> registros
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Cliente</th>
                <th>Productos</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {sales.map((sale) => (
                <tr key={sale.id}>
                  <td>{sale.sale_date}</td>
                  <td>{customerName(sale.customer_id)}</td>
                  <td>{saleProducts(sale)}</td>
                  <td>
                    <span
                      className={`status ${sale.status === "CONFIRMADA" ? "success" : "neutral"}`}
                    >
                      {sale.status.replaceAll("_", " ")}
                    </span>
                  </td>
                </tr>
              ))}
              {!sales.length && (
                <tr>
                  <td colSpan={4}>No hay ventas registradas.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      {open && (
        <Modal title="Registrar venta" onClose={closeSale}>
          <form onSubmit={submit}>
            <div className="form-grid">
              <label>
                Cliente
                <select
                  value={customerId}
                  onChange={(event) =>
                    event.target.value === "__create__"
                      ? setCustomerModal(true)
                      : setCustomerId(event.target.value)
                  }
                  required
                >
                  <option value="">Selecciona un cliente</option>
                  <option value="__create__">Crear cliente</option>
                  {customers.map((customer) => (
                    <option key={customer.id} value={customer.id}>
                      {customer.last_names} {customer.first_names} - {customer.dni}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Fecha de venta
                <input
                  name="sale_date"
                  type="date"
                  defaultValue={new Date().toISOString().slice(0, 10)}
                  required
                />
              </label>
              <label>
                Canal de primera venta
                <select value={channel} onChange={(event) => setChannel(event.target.value)}>
                  <option value="TV">TV</option>
                  <option value="DIGITAL">Digital</option>
                  <option value="OTROS">Otros</option>
                </select>
              </label>
              {channel === "OTROS" && (
                <label>
                  Detalle del canal
                  <input name="acquisition_channel_detail" required />
                </label>
              )}
            </div>
            <div className="sale-lines">
              <h3>Productos</h3>
              {lines.map((line, index) => (
                <div className="sale-line" key={index}>
                  <select
                    value={line.product_id}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? { ...item, product_id: event.target.value } : item,
                        ),
                      )
                    }
                    required
                  >
                    <option value="">Selecciona un producto</option>
                    {products.map((product) => (
                      <option key={product.id} value={product.id}>
                        {product.name} ({product.code})
                      </option>
                    ))}
                  </select>
                  <input
                    aria-label="Cantidad"
                    type="number"
                    min="1"
                    value={line.quantity}
                    onChange={(event) =>
                      setLines((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index
                            ? { ...item, quantity: Number(event.target.value) }
                            : item,
                        ),
                      )
                    }
                    required
                  />
                  {lines.length > 1 && (
                    <button
                      className="secondary"
                      type="button"
                      onClick={() =>
                        setLines((current) => current.filter((_, itemIndex) => itemIndex !== index))
                      }
                    >
                      Quitar
                    </button>
                  )}
                </div>
              ))}
              <button
                className="secondary"
                type="button"
                onClick={() => setLines((current) => [...current, { product_id: "", quantity: 1 }])}
              >
                Agregar producto
              </button>
            </div>
            <label className="notes">
              Notas opcionales
              <textarea name="notes" maxLength={4000} />
            </label>
            {error && <p className="form-error">{error}</p>}
            <footer>
              <button type="button" className="secondary" onClick={closeSale}>
                Cancelar
              </button>
              <button>Guardar venta</button>
            </footer>
          </form>
        </Modal>
      )}
      {customerModal && (
        <CrudModal
          title="Crear cliente"
          fields={customerFields}
          onClose={() => setCustomerModal(false)}
          onSave={saveCustomer}
        />
      )}
    </>
  );
}
