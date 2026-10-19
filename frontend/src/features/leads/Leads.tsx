import { useEffect, useState } from "react";
import { CustomerModal } from "../../components/CustomerModal";
import { DataPanel } from "../../components/DataPanel";
import { Modal } from "../../components/Modal";
import { PageHeader } from "../../components/PageHeader";
import { SearchSelect } from "../../components/SearchSelect";
import { api, download, listAll, upload } from "../../services/api";
import type {
  Customer,
  Lead,
  LeadActivity,
  Paged,
  Product,
  TypificationTree,
  User,
} from "../../services/types";

type BoardStatus = "PENDIENTE" | "AGENDADO" | "RECUPERABLE" | "CERRADO";
type SaleLine = { product_id: string; quantity: number };
type ConversionContext = { typificationId: string; channel: string; activityNote: string };
type BoardSummary = Partial<Record<BoardStatus, number | { total: number }>>;
type ImportPreview = {
  id: string;
  state: string;
  total_rows: number;
  valid_rows: number;
  rejected_rows: number;
  errors: Array<{ row_number?: number | null; message: string }>;
};

const BOARD_SIZE = 4;
const ACTIVITY_PAGE_SIZE = 10;
const columns: Array<{ key: BoardStatus; title: string }> = [
  { key: "PENDIENTE", title: "Pendientes" },
  { key: "AGENDADO", title: "Agendados" },
  { key: "RECUPERABLE", title: "Recuperables" },
  { key: "CERRADO", title: "Cerrados" },
];
const sourceOptions = [
  ["", "Todos los orígenes"],
  ["REDES_SOCIALES", "Redes sociales"],
  ["COMERCIAL_TV", "Comercial TV"],
  ["REFERIDO", "Referido"],
] as const;

function emptyPage(): Paged<Lead> {
  return { items: [], page: 1, page_size: BOARD_SIZE, total: 0, pages: 0 };
}
function emptyActivityPage(): Paged<LeadActivity> {
  return { items: [], page: 1, page_size: ACTIVITY_PAGE_SIZE, total: 0, pages: 0 };
}
function formatDate(value?: string | null, time = false) {
  if (!value) return "Sin registro";
  return new Intl.DateTimeFormat("es-PE", {
    dateStyle: "medium",
    ...(time ? { timeStyle: "short" } : {}),
  }).format(new Date(time ? value : `${value}T00:00:00`));
}
function localDate() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString().slice(0, 10);
}
function parseLocalDate(value: string) {
  return new Date(`${value}T00:00:00`);
}
function dateValue(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}
function periodLabel(from: string, to: string) {
  const formatter = new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", year: "numeric" });
  return `${formatter.format(parseLocalDate(from))} - ${formatter.format(parseLocalDate(to))}`;
}
function PeriodPicker({ from, to, onChange }: { from: string; to: string; onChange: (from: string, to: string) => void }) {
  const [open, setOpen] = useState(false);
  const [draftFrom, setDraftFrom] = useState(from);
  const [draftTo, setDraftTo] = useState(to);
  const [month, setMonth] = useState(() => {
    const date = parseLocalDate(from);
    return new Date(date.getFullYear(), date.getMonth(), 1);
  });
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1);
  const start = (firstDay.getDay() + 6) % 7;
  const days = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells = Array.from({ length: start + days }, (_, index) => index < start ? null : new Date(month.getFullYear(), month.getMonth(), index - start + 1));
  const choose = (date: Date) => {
    const value = dateValue(date);
    if (!draftFrom) {
      setDraftFrom(value);
      setDraftTo("");
      return;
    }
    if (!draftTo) {
      setDraftFrom(value < draftFrom ? value : draftFrom);
      setDraftTo(value < draftFrom ? draftFrom : value);
      return;
    }
    if (value < draftFrom) setDraftFrom(value);
    else setDraftTo(value);
  };
  const monthTitle = new Intl.DateTimeFormat("es-PE", { month: "long", year: "numeric" }).format(month);
  return (
    <div className="lead-period-picker">
      <span>Periodo de gestión</span>
      <button type="button" className="lead-period-trigger" onClick={() => { setDraftFrom(from); setDraftTo(to); setOpen((value) => !value); }} aria-expanded={open}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18" /></svg>
        {to ? periodLabel(from, to) : `${new Intl.DateTimeFormat("es-PE", { day: "numeric", month: "short", year: "numeric" }).format(parseLocalDate(from))} - Selecciona fecha final`}
      </button>
      {open && (
        <div className="lead-calendar" role="dialog" aria-label="Seleccionar periodo de gestión">
          <header>
            <strong>{monthTitle.charAt(0).toUpperCase() + monthTitle.slice(1)}</strong>
            <span>
              <button type="button" aria-label="Mes anterior" onClick={() => setMonth((value) => new Date(value.getFullYear(), value.getMonth() - 1, 1))}>‹</button>
              <button type="button" aria-label="Mes siguiente" onClick={() => setMonth((value) => new Date(value.getFullYear(), value.getMonth() + 1, 1))}>›</button>
            </span>
          </header>
          <div className="lead-calendar-weekdays">{["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"].map((day) => <span key={day}>{day}</span>)}</div>
          <div className="lead-calendar-days">
            {cells.map((date, index) => {
              if (!date) return <span key={`blank-${index}`} />;
              const value = dateValue(date);
              const selected = value === draftFrom || value === draftTo;
              const between = Boolean(draftTo && value > draftFrom && value < draftTo);
              return <button type="button" key={value} className={`${selected ? "selected" : ""} ${between ? "between" : ""}`} onClick={() => choose(date)} onDoubleClick={() => { setDraftFrom(value); setDraftTo(""); }}>{date.getDate()}</button>;
            })}
          </div>
          <footer>
            <button type="button" className="secondary" onClick={() => setOpen(false)}>Cancelar</button>
            <button type="button" disabled={!draftFrom || !draftTo} onClick={() => { onChange(draftFrom, draftTo); setOpen(false); }}>Aplicar periodo</button>
          </footer>
        </div>
      )}
    </div>
  );
}
function statusLabel(status: string) {
  return status.replace("CERRADO_", "").replaceAll("_", " ");
}
function closureLabel(lead: Lead) {
  return lead.status === "CERRADO_EFECTIVO"
    ? "Venta conseguida"
    : lead.latest_typification_name || "Cerrado sin conversión";
}
function FlowIcon({ status }: { status: BoardStatus }) {
  const paths = {
    PENDIENTE: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4M17 3v4M3 10h18M8 14h3M8 18h5" /></>,
    AGENDADO: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    RECUPERABLE: <path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5" />,
    CERRADO: <><circle cx="12" cy="12" r="9" /><path d="m8 12 2.5 2.5L16 9" /></>,
  }[status];
  return <svg className="lead-column-icon" viewBox="0 0 24 24" aria-hidden="true">{paths}</svg>;
}
function typificationOptions(
  nodes: TypificationTree[],
  depth = 0,
): Array<{ value: string; label: string }> {
  return nodes.flatMap((node) => [
    { value: node.id, label: `${"  ".repeat(depth)}${node.name}` },
    ...typificationOptions(node.children, depth + 1),
  ]);
}
function activeLeaves(nodes: TypificationTree[]): TypificationTree[] {
  return nodes.filter((node) => node.is_active).flatMap((node) =>
    node.children.length ? activeLeaves(node.children) : node.lead_outcome ? [node] : [],
  );
}
function summaryTotal(summary: BoardSummary, status: BoardStatus, fallback: number) {
  const value = summary[status];
  return typeof value === "number" ? value : (value?.total ?? fallback);
}

export function Leads({ user }: { user: User }) {
  const [board, setBoard] = useState<Record<BoardStatus, Paged<Lead>>>({
    PENDIENTE: emptyPage(),
    AGENDADO: emptyPage(),
    RECUPERABLE: emptyPage(),
    CERRADO: emptyPage(),
  });
  const [summary, setSummary] = useState<BoardSummary>({});
  const [loading, setLoading] = useState<Partial<Record<BoardStatus, boolean>>>({});
  const [filters, setFilters] = useState({
    q: "",
    source: "",
    advisor_id: "",
    initial_product_id: "",
    activity_from: localDate(),
    activity_to: localDate(),
    next_action: "",
    typification_id: "",
  });
  const [products, setProducts] = useState<Product[]>([]);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [advisors, setAdvisors] = useState<User[]>([]);
  const [typifications, setTypifications] = useState<TypificationTree[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(null);
  const [importing, setImporting] = useState(false);
  const [selected, setSelected] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<Paged<LeadActivity>>(emptyActivityPage);
  const [parentId, setParentId] = useState("");
  const [childId, setChildId] = useState("");
  const [conversion, setConversion] = useState<ConversionContext | null>(null);
  const [customerModalOpen, setCustomerModalOpen] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [customerPayload, setCustomerPayload] = useState<Record<string, string | undefined> | null>(
    null,
  );
  const [lines, setLines] = useState<SaleLine[]>([{ product_id: "", quantity: 1 }]);
  const [error, setError] = useState("");

  const queryFor = (status: BoardStatus, page: number, active = filters) => {
    const query = new URLSearchParams({
      status,
      page: String(page),
      page_size: String(BOARD_SIZE),
    });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    if (status === "AGENDADO" && !active.next_action) query.set("next_action", "DUE");
    return query;
  };
  const loadColumn = async (status: BoardStatus, page = 1, active = filters, append = false) => {
    setLoading((current) => ({ ...current, [status]: true }));
    try {
      const result = await api<Paged<Lead>>(`/leads/board?${queryFor(status, page, active)}`);
      setBoard((current) => ({
        ...current,
        [status]: append
          ? { ...result, items: [...current[status].items, ...result.items] }
          : result,
      }));
      return result;
    } finally {
      setLoading((current) => ({ ...current, [status]: false }));
    }
  };
  const loadBoard = async (active = filters, reset = true) => {
    const pages = reset
      ? { PENDIENTE: 1, AGENDADO: 1, RECUPERABLE: 1, CERRADO: 1 }
      : (Object.fromEntries(columns.map(({ key }) => [key, board[key].page])) as Record<
          BoardStatus,
          number
        >);
    const [nextSummary, ...pagesLoaded] = await Promise.all([
      api<BoardSummary>(
        `/leads/board-summary?${new URLSearchParams(Object.entries(active).filter(([, value]) => Boolean(value)))}`,
      ),
      ...columns.map(({ key }) => loadColumn(key, pages[key], active)),
    ]);
    const scheduled = pagesLoaded[columns.findIndex(({ key }) => key === "AGENDADO")];
    setSummary({ ...nextSummary, AGENDADO: scheduled.total });
  };

  useEffect(() => {
    loadBoard().catch(() => setError("No fue posible cargar el tablero de leads."));
    Promise.all([
      listAll<Product>("/products"),
      api<Customer[]>("/customers/sale-options"),
      api<TypificationTree[]>("/configuration/contact-typifications/tree"),
      user.role === "ASESOR" ? Promise.resolve([]) : api<User[]>("/users/advisors"),
    ])
      .then(([productRows, customerRows, typificationRows, advisorRows]) => {
        setProducts(productRows.filter((product) => product.is_active));
        setCustomers(customerRows);
        setTypifications(typificationRows);
        setAdvisors(advisorRows);
      })
      .catch(() => setError("No fue posible cargar los catálogos de leads."));
  }, []);

  const openLead = async (lead: Lead) => {
    setSelected(lead);
    setParentId("");
    setChildId("");
    setConversion(null);
    setCustomerPayload(null);
    setCustomerId("");
    setLines([{ product_id: "", quantity: 1 }]);
    setError("");
    try {
      await loadActivities(lead.id);
    } catch {
      setActivities(emptyActivityPage());
    }
  };
  const loadActivities = async (leadId: string, page = 1, append = false) => {
    const result = await api<Paged<LeadActivity>>(
      `/leads/${leadId}/activities?page=${page}&page_size=${ACTIVITY_PAGE_SIZE}`,
    );
    setActivities((current) =>
      append ? { ...result, items: [...current.items, ...result.items] } : result,
    );
  };
  const refreshSelected = async (leadId: string) => {
    const [lead] = await Promise.all([api<Lead>(`/leads/${leadId}`), loadActivities(leadId)]);
    setSelected(lead);
    await loadBoard(filters, false);
  };
  const roots = typifications.filter(
    (item) => item.is_active && (Boolean(item.lead_outcome) || activeLeaves(item.children).length > 0),
  );
  const parent = roots.find((item) => item.id === parentId);
  const children = parent ? activeLeaves(parent.children) : [];
  const selectedCustomer = customers.find((customer) => customer.id === customerId);
  const typification =
    children.find((item) => item.id === childId) ||
    (parent && !parent.children.length ? parent : undefined);

  const saveActivity = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected || !typification?.lead_outcome) return;
    const form = new FormData(event.currentTarget);
    const channel = String(form.get("channel"));
    const note = String(form.get("note") || "");
    if (typification.lead_outcome === "EFECTIVO") {
      setConversion({ typificationId: typification.id, channel, activityNote: note });
      return;
    }
    const date =
      typification.lead_outcome === "AGENDADO" ? String(form.get("next_action_date") || "") : "";
    const time =
      typification.lead_outcome === "AGENDADO" ? String(form.get("next_action_time") || "") : "";
    try {
      await api(`/leads/${selected.id}/activities`, {
        method: "POST",
        body: JSON.stringify({
          channel,
          typification_id: typification.id,
          note: note || undefined,
          next_action_date: date || undefined,
          next_action_at: date && time ? new Date(`${date}T${time}`).toISOString() : undefined,
        }),
      });
      setParentId("");
      setChildId("");
      await refreshSelected(selected.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible registrar la atención.");
    }
  };
  const convertLead = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      !selected ||
      !conversion ||
      (!customerId && !customerPayload) ||
      lines.some(
        (line) => !line.product_id || !Number.isInteger(line.quantity) || line.quantity < 1,
      )
    )
      return;
    const form = new FormData(event.currentTarget);
    try {
      await api(`/leads/${selected.id}/convert`, {
        method: "POST",
        body: JSON.stringify({
          typification_id: conversion.typificationId,
          channel: conversion.channel,
          activity_note: conversion.activityNote || undefined,
          customer_id: customerPayload ? undefined : customerId,
          customer: customerPayload || undefined,
          customer_condition: form.get("customer_condition") || undefined,
          sale_date: form.get("sale_date"),
          items: lines,
          notes: form.get("notes") || undefined,
        }),
      });
      setConversion(null);
      await refreshSelected(selected.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible convertir el lead.");
    }
  };
  const saveAssignment = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    const form = new FormData(event.currentTarget);
    try {
      await api(`/leads/${selected.id}/assign`, {
        method: "POST",
        body: JSON.stringify({
          assigned_advisor_id: form.get("advisor_id") || null,
          reason: form.get("reason"),
        }),
      });
      await refreshSelected(selected.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible asignar el lead.");
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="PROSPECCIÓN"
        title="Leads"
        description="Gestiona cada prospecto mediante tipificaciones y convierte solo los resultados efectivos."
        actions={
          <>
            {user.role !== "ASESOR" && (
              <button type="button" className="secondary" onClick={() => setImportOpen(true)}>
                Importar leads
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setCreateOpen(true);
                setError("");
              }}
            >
              Nuevo lead
            </button>
          </>
        }
      />
      {error && <p className="error-message">{error}</p>}
      <DataPanel
        title="Tablero de leads"
        description="Cada columna carga sus propios resultados."
        metric={
          <span className="header-metric">
            {columns.reduce(
              (total, { key }) => total + summaryTotal(summary, key, board[key].total),
              0,
            )}{" "}
            registros
          </span>
        }
      >
        <form
          className="filters lead-filters"
          onSubmit={(event) => {
            event.preventDefault();
            setError("");
            loadBoard(filters).catch((reason) =>
              setError(reason instanceof Error ? reason.message : "No fue posible filtrar."),
            );
          }}
        >
          <div className="filter-grid">
            <label>
              Buscar
              <input
                placeholder="Nombre, teléfono o correo"
                value={filters.q}
                onChange={(event) => setFilters((value) => ({ ...value, q: event.target.value }))}
              />
            </label>
            <label>
              Origen
              <select
                value={filters.source}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, source: event.target.value }))
                }
              >
                {sourceOptions.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            {user.role !== "ASESOR" && (
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
              Producto de interés
              <select
                value={filters.initial_product_id}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, initial_product_id: event.target.value }))
                }
              >
                <option value="">Todos los productos</option>
                {products.map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </select>
            </label>
            <PeriodPicker
              from={filters.activity_from}
              to={filters.activity_to}
              onChange={(activity_from, activity_to) => setFilters((value) => ({ ...value, activity_from, activity_to }))}
            />
            <label>
              Próxima acción
              <select
                value={filters.next_action}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, next_action: event.target.value }))
                }
              >
                <option value="">Todas</option>
                <option value="OVERDUE">Vencida</option>
                <option value="TODAY">Hoy</option>
                <option value="NEXT_7">Próximos 7 días</option>
                <option value="UNSCHEDULED">Sin agendar</option>
              </select>
            </label>
            <label>
              Última tipificación
              <select
                value={filters.typification_id}
                onChange={(event) =>
                  setFilters((value) => ({ ...value, typification_id: event.target.value }))
                }
              >
                <option value="">Todas las tipificaciones</option>
                {typificationOptions(typifications).map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button>Aplicar filtros</button>
          </div>
        </form>
        <div className="lead-kanban">
          {columns.map(({ key, title }) => {
            const page = board[key];
            const total = summaryTotal(summary, key, page.total);
            return (
              <section className={`lead-kanban-column lead-kanban-column-${key.toLowerCase()}`} key={key}>
                <header>
                  <span><FlowIcon status={key} />{title}</span>
                  <b>{total}</b>
                </header>
                <div className="lead-kanban-cards">
                  {page.items.map((lead) => (
                    <article
                      className={`lead-card lead-${lead.status.toLowerCase()}`}
                      key={lead.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => void openLead(lead)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          void openLead(lead);
                        }
                      }}
                    >
                      <div className="lead-card-heading">
                        <b>{lead.full_name}</b>
                        <span className="lead-source">{lead.source.replaceAll("_", " ")}</span>
                      </div>
                      {lead.status === "PENDIENTE" && lead.reassigned_from_recovery && (
                        <span className="lead-reassigned">Reasignado desde recuperación</span>
                      )}
                      {lead.status === "RECUPERABLE" && (
                        <span className="lead-recovery-typification">
                          Gestión: {lead.latest_typification_name || "Sin gestión registrada"}
                        </span>
                      )}
                      {lead.status.startsWith("CERRADO_") && (
                        <span className={`lead-closure lead-closure-${lead.status.toLowerCase()}`}>
                          {closureLabel(lead)}
                        </span>
                      )}
                        <div className="lead-card-contact">
                          <span>Teléfono</span>
                          <b>{lead.phone}</b>
                        </div>
                        <small className="lead-card-product">
                          {products.find((product) => product.id === lead.initial_product_id)?.name ||
                            "Sin producto de interés"}
                        </small>
                      {lead.next_action_date && (
                        <div className="lead-card-action">
                          <span>Próxima acción</span>
                          <b>
                            {formatDate(
                              lead.next_action_at || lead.next_action_date,
                              Boolean(lead.next_action_at),
                            )}
                          </b>
                        </div>
                      )}
                      <footer>
                        <span>{lead.assigned_advisor_name || "Sin asignar"}</span>
                      </footer>
                    </article>
                  ))}
                  {!page.items.length && !loading[key] && (
                    <p className="lead-kanban-empty">Sin leads en este estado.</p>
                  )}
                </div>
                {page.items.length < total && (
                  <button
                    className="secondary lead-load-more"
                    disabled={loading[key]}
                    onClick={() =>
                      loadColumn(key, page.page + 1, filters, true).catch(() =>
                        setError("No fue posible cargar más leads."),
                      )
                    }
                  >
                    {loading[key] ? "Cargando..." : "Cargar 4 más"}
                  </button>
                )}
              </section>
            );
          })}
        </div>
      </DataPanel>
      {createOpen && (
        <Modal title="Registrar lead" onClose={() => setCreateOpen(false)}>
          <form
            onSubmit={async (event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              try {
                const lead = await api<Lead>("/leads", {
                  method: "POST",
                  body: JSON.stringify({
                    full_name: form.get("full_name"),
                    phone: form.get("phone"),
                    email: form.get("email") || undefined,
                    source: form.get("source"),
                    initial_product_id: form.get("initial_product_id") || undefined,
                    notes: form.get("notes") || undefined,
                    assigned_advisor_id:
                      user.role === "ASESOR"
                        ? undefined
                        : form.get("assigned_advisor_id") || undefined,
                  }),
                });
                const manageNow = form.get("manage_now") === "on";
                setCreateOpen(false);
                void loadBoard(filters).catch(() =>
                  setError("El lead fue registrado, pero no fue posible actualizar el tablero."),
                );
                if (manageNow) void openLead(lead);
              } catch (reason) {
                setError(
                  reason instanceof Error ? reason.message : "No fue posible registrar el lead.",
                );
              }
            }}
          >
            <div className="form-grid">
              <label>
                Nombre completo
                <input name="full_name" required minLength={2} />
              </label>
              <label>
                Teléfono
                <input name="phone" required minLength={6} />
              </label>
              <label>
                Origen
                <select name="source" defaultValue="REDES_SOCIALES">
                  {sourceOptions.slice(1).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Producto de interés
                <select name="initial_product_id">
                  <option value="">Sin definir</option>
                  {products.map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Correo
                <input name="email" type="email" />
              </label>
              {user.role !== "ASESOR" && (
                <label>
                  Asesor responsable
                  <select name="assigned_advisor_id">
                    <option value="">Asignar después</option>
                    {advisors.map((advisor) => (
                      <option key={advisor.id} value={advisor.id}>
                        {advisor.full_name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
               <label className="notes">
                 Notas
                 <textarea name="notes" maxLength={4000} />
               </label>
               <label className="checkbox-field notes">
                 <input name="manage_now" type="checkbox" defaultChecked />
                 Registrar y gestionar ahora
               </label>
            </div>
            <footer>
              <button type="button" className="secondary" onClick={() => setCreateOpen(false)}>
                Cancelar
              </button>
              <button>Registrar lead</button>
            </footer>
          </form>
        </Modal>
      )}
      {importOpen && (
        <Modal
          title="Importar leads asignados"
          onClose={() => {
            setImportOpen(false);
            setImportPreview(null);
          }}
        >
          <p>Descarga la plantilla, asigna cada fila mediante el correo del asesor y carga el archivo. Los leads se crearán como pendientes.</p>
          <div className="lead-import-actions">
            <button type="button" className="secondary" onClick={() => void download("/imports/templates/leads", "plantilla_leads.xlsx")}>
              Descargar plantilla
            </button>
            <label className="file-upload">
              Seleccionar archivo Excel
              <input
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                disabled={importing}
                onChange={async (event) => {
                  const file = event.target.files?.[0];
                  if (!file) return;
                  setImporting(true);
                  setError("");
                  try {
                    const form = new FormData();
                    form.append("file", file);
                    setImportPreview(await upload<ImportPreview>("/imports/leads/preview", form));
                  } catch (reason) {
                    setError(reason instanceof Error ? reason.message : "No fue posible validar el archivo.");
                  } finally {
                    setImporting(false);
                  }
                }}
              />
            </label>
          </div>
          {importPreview && (
            <section className="lead-import-preview">
              <p><b>{importPreview.valid_rows}</b> de {importPreview.total_rows} filas listas para importar.</p>
              {importPreview.rejected_rows > 0 && (
                <ul>
                  {importPreview.errors.slice(0, 5).map((item, index) => (
                    <li key={`${item.row_number}-${index}`}>Fila {item.row_number || "general"}: {item.message}</li>
                  ))}
                </ul>
              )}
              {importPreview.state === "PREVIEW_READY" && (
                <button
                  type="button"
                  disabled={importing}
                  onClick={async () => {
                    setImporting(true);
                    try {
                      await api(`/imports/${importPreview.id}/commit`, { method: "POST" });
                      setImportOpen(false);
                      setImportPreview(null);
                      await loadBoard(filters);
                    } catch (reason) {
                      setError(reason instanceof Error ? reason.message : "No fue posible importar los leads.");
                    } finally {
                      setImporting(false);
                    }
                  }}
                >
                  {importing ? "Importando..." : "Confirmar importación"}
                </button>
              )}
            </section>
          )}
        </Modal>
      )}
      {selected && (
        <Modal title={`Gestionar lead: ${selected.full_name}`} onClose={() => setSelected(null)}>
          <div className="alert-summary alert-context">
            <div>
              <span>Contacto</span>
              <b>{selected.phone}</b>
              <small>{selected.email || "Sin correo"}</small>
            </div>
            <div>
              <span>Estado</span>
              <b>{statusLabel(selected.status)}</b>
              <small>{selected.assigned_advisor_name || "Sin asignar"}</small>
            </div>
            <div>
              <span>Próxima acción</span>
              <b>
                {formatDate(
                  selected.next_action_at || selected.next_action_date,
                  Boolean(selected.next_action_at),
                )}
              </b>
            </div>
          </div>
          {!conversion && !selected.status.startsWith("CERRADO") && (
            <form className="alert-management-form" onSubmit={saveActivity}>
              <div className="form-grid">
                <label>
                  Tipificación
                  <select
                    value={parentId}
                    onChange={(event) => {
                      setParentId(event.target.value);
                      setChildId("");
                    }}
                    required
                  >
                    <option value="">Selecciona una tipificación</option>
                    {roots.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Subtipificación
                  <select
                    value={childId}
                    onChange={(event) => setChildId(event.target.value)}
                    disabled={!parent || !children.length}
                    required={Boolean(parent && children.length)}
                  >
                    <option value="">
                      {parent
                        ? "Selecciona una subtipificación"
                        : "Selecciona primero una tipificación"}
                    </option>
                    {children.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Canal
                  <select name="channel" defaultValue="LLAMADA">
                    <option value="LLAMADA">Llamada</option>
                    <option value="WHATSAPP">WhatsApp</option>
                  </select>
                </label>
                {typification?.lead_outcome === "AGENDADO" && (
                  <>
                    <label>
                      Próxima acción
                      <input name="next_action_date" type="date" required />
                    </label>
                    <label>
                      Hora de recordatorio
                      <input name="next_action_time" type="time" required />
                    </label>
                  </>
                )}
                <label className="notes">
                  Nota
                  <textarea name="note" required={typification?.requires_note} maxLength={4000} />
                </label>
              </div>
              {typification && !typification.lead_outcome && (
                <p className="form-error">
                  La tipificación final debe tener un resultado de lead configurado.
                </p>
              )}
              <footer>
                <button disabled={!typification?.lead_outcome}>
                  {typification?.lead_outcome === "EFECTIVO"
                    ? "Continuar a venta"
                    : "Registrar atención"}
                </button>
              </footer>
            </form>
          )}
          {conversion && (
            <section className="lead-conversion">
              <h3>Registrar venta efectiva</h3>
              <p>La atención se registrará junto con la conversión.</p>
              <form className="sale-form" onSubmit={convertLead}>
                <div className="form-grid sale-details-grid">
                  <label>
                    Cliente
                    <SearchSelect
                      value={customerId}
                      onChange={(value) => {
                        setCustomerId(value);
                        setCustomerPayload(null);
                      }}
                      required={!customerPayload}
                      placeholder="Busca por nombre o DNI"
                      actionLabel="Crear cliente"
                      onAction={() => setCustomerModalOpen(true)}
                      options={customers.map((customer) => ({
                        value: customer.id,
                        label: `${customer.last_names} ${customer.first_names} - ${customer.dni}`,
                      }))}
                    />
                    <small>La venta se registrará a nombre del asesor asignado al lead.</small>
                  </label>
                  {selectedCustomer && (
                    <label className="notes" key={selectedCustomer.id}>
                      Enfermedad o condición
                      <textarea
                        name="customer_condition"
                        defaultValue={selectedCustomer.condition || ""}
                        maxLength={500}
                        placeholder="Sin información"
                      />
                    </label>
                  )}
                  <label>
                    Fecha de venta
                    <input
                      name="sale_date"
                      type="date"
                      defaultValue={new Date().toISOString().slice(0, 10)}
                      required
                    />
                  </label>
                </div>
                {customerPayload && (
                  <p className="success-message">Nuevo cliente listo para registrar con esta venta.</p>
                )}
                <div className="sale-lines">
                  <h3>Productos</h3>
                  {lines.map((line, index) => (
                    <div className="sale-line" key={index}>
                      <SearchSelect
                        value={line.product_id}
                        onChange={(product_id) =>
                          setLines((rows) =>
                            rows.map((row, rowIndex) =>
                              rowIndex === index ? { ...row, product_id } : row,
                            ),
                          )
                        }
                        required
                        placeholder="Busca por código o nombre"
                        options={products.map((product) => ({
                          value: product.id,
                          label: `${product.name} (${product.code})`,
                        }))}
                      />
                      <input
                        aria-label="Cantidad"
                        type="number"
                        min="1"
                        step="1"
                        value={line.quantity}
                        onChange={(event) =>
                          setLines((rows) =>
                            rows.map((row, rowIndex) =>
                              rowIndex === index
                                ? { ...row, quantity: Number(event.target.value) }
                                : row,
                            ),
                          )
                        }
                        required
                      />
                      {lines.length > 1 && (
                        <button
                          type="button"
                          className="secondary"
                          onClick={() =>
                            setLines((rows) => rows.filter((_, rowIndex) => rowIndex !== index))
                          }
                        >
                          Quitar
                        </button>
                      )}
                    </div>
                  ))}
                  <button
                    type="button"
                    className="secondary sale-add-product"
                    onClick={() => setLines((rows) => [...rows, { product_id: "", quantity: 1 }])}
                  >
                    Agregar producto
                  </button>
                </div>
                <label className="notes sale-notes">
                  Notas opcionales
                  <textarea name="notes" maxLength={4000} />
                </label>
                <footer>
                  <button>Confirmar venta y convertir</button>
                </footer>
              </form>
            </section>
          )}
          {selected.status === "RECUPERABLE" && user.role !== "ASESOR" && (
            <form className="alert-management-form" onSubmit={saveAssignment}>
              <h3>Asignar recuperación</h3>
              <div className="form-grid">
                <label>
                  Asesor
                  <select
                    name="advisor_id"
                    defaultValue={selected.assigned_advisor_id || ""}
                    required
                  >
                    <option value="">Selecciona un asesor</option>
                    {advisors.map((advisor) => (
                      <option key={advisor.id} value={advisor.id}>
                        {advisor.full_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="notes">
                  Motivo
                  <textarea name="reason" required minLength={3} />
                </label>
              </div>
              <footer>
                <button>Asignar lead</button>
              </footer>
            </form>
          )}
          <section className="lead-history">
            <div className="lead-history-heading">
              <h3>Historial de atenciones</h3>
              {activities.total > 0 && <span>{activities.total} registros</span>}
            </div>
            {activities.items.length ? (
              <ol className="lead-history-list">
                {activities.items.map((activity) => (
                  <li key={activity.id}>
                    <div className="lead-history-marker" aria-hidden="true" />
                    <article>
                      <div className="lead-history-entry-heading">
                        <b>{activity.typification_name || "Gestión"}</b>
                        <time>{formatDate(activity.created_at, true)}</time>
                      </div>
                      <span>
                        {activity.channel} · {activity.advisor_name || "Usuario"}
                      </span>
                      {activity.note && <p>{activity.note}</p>}
                    </article>
                  </li>
                ))}
              </ol>
            ) : (
              <p>Sin atenciones registradas.</p>
            )}
            {activities.items.length < activities.total && selected && (
              <button
                type="button"
                className="secondary lead-history-more"
                onClick={() => void loadActivities(selected.id, activities.page + 1, true)}
              >
                Ver 10 atenciones anteriores
              </button>
            )}
          </section>
          {user.role !== "ASESOR" && (
            <footer>
              <button
                type="button"
                className="danger"
                onClick={async () => {
                  if (!window.confirm("¿Eliminar este lead de forma permanente?")) return;
                  try {
                    await api(`/leads/${selected.id}`, { method: "DELETE" });
                    setSelected(null);
                    await loadBoard(filters, false);
                  } catch (reason) {
                    setError(
                      reason instanceof Error ? reason.message : "No fue posible eliminar el lead.",
                    );
                  }
                }}
              >
                Eliminar lead
              </button>
            </footer>
          )}
        </Modal>
      )}
      {customerModalOpen && (
        <CustomerModal
          customer={null}
          role={user.role}
          title="Crear cliente para conversión"
          onClose={() => setCustomerModalOpen(false)}
          onSave={async (data) => {
            setCustomerPayload(data);
            setCustomerId("");
          }}
        />
      )}
    </>
  );
}
