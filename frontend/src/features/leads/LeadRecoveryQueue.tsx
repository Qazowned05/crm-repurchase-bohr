import { useEffect, useState } from "react";
import { DataPanel } from "../../components/DataPanel";
import { PageHeader } from "../../components/PageHeader";
import { PAGE_SIZE, Pagination } from "../../components/Pagination";
import { api, listAll } from "../../services/api";
import type { Campaign, Lead, Paged, Product, User } from "../../services/types";

const emptyPage = (): Paged<Lead> => ({ items: [], page: 1, page_size: PAGE_SIZE, total: 0, pages: 0 });

export function LeadRecoveryQueue() {
  const [leads, setLeads] = useState<Paged<Lead>>(emptyPage);
  const [advisors, setAdvisors] = useState<User[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState({ q: "", campaign_id: "", advisor_id: "", initial_product_id: "", created_on: "" });
  const load = async (page = 1, active = filters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(active).forEach(([key, value]) => value && query.set(key, value));
    const result = await api<Paged<Lead>>(`/leads/recovery?${query}`);
    setLeads(result);
  };
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar los leads recuperables."));
    api<User[]>("/users/advisors").then(setAdvisors).catch(() => {});
    listAll<Product>("/products").then((rows) => setProducts(rows.filter((product) => product.is_active))).catch(() => {});
    listAll<Campaign>("/campaigns?active_only=true").then(setCampaigns).catch(() => {});
  }, []);
  return (
    <>
      <PageHeader
        eyebrow="SEGUIMIENTO"
        title="Leads recuperables"
        description="Consulta los leads que requieren una nueva oportunidad. Reasígnalos desde el Kanban de Leads."
        meta={<span className="header-metric">{leads.total} recuperables</span>}
      />
      {error && <p className="error-message">{error}</p>}
      <section className="panel filters">
        <div className="panel-heading"><div><h2>Filtros</h2><p>Acota la consulta de leads recuperables.</p></div></div>
        <form onSubmit={(event) => { event.preventDefault(); void load(1).catch(() => setError("No fue posible aplicar los filtros.")); }}>
          <div className="filter-grid">
            <label>Buscar<input placeholder="Nombre, teléfono o correo" value={filters.q} onChange={(event) => setFilters((value) => ({ ...value, q: event.target.value }))} /></label>
            <label>Campaña<select value={filters.campaign_id} onChange={(event) => setFilters((value) => ({ ...value, campaign_id: event.target.value }))}><option value="">Todas las campañas</option>{campaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.name}</option>)}</select></label>
            <label>Asesor<select value={filters.advisor_id} onChange={(event) => setFilters((value) => ({ ...value, advisor_id: event.target.value }))}><option value="">Todos los asesores</option>{advisors.map((advisor) => <option key={advisor.id} value={advisor.id}>{advisor.full_name}</option>)}</select></label>
            <label>Producto de interés<select value={filters.initial_product_id} onChange={(event) => setFilters((value) => ({ ...value, initial_product_id: event.target.value }))}><option value="">Todos los productos</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label>
            <label>Fecha de registro<input type="date" value={filters.created_on} onChange={(event) => setFilters((value) => ({ ...value, created_on: event.target.value }))} /></label>
            <button>Aplicar filtros</button>
          </div>
        </form>
      </section>
      <DataPanel
        title="Cola de recuperables"
        description="Solo muestra leads recuperables; la reasignación se realiza desde el Kanban de Leads."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                 <th>Lead</th><th>Campaña</th><th>Última tipificación</th><th>Asesor actual</th><th>Registrado</th>
              </tr>
            </thead>
            <tbody>
              {leads.items.map((lead) => (
                <tr key={lead.id}>
                  <td><b>{lead.full_name}</b><small className="table-detail">{lead.phone}</small></td>
                  <td>{lead.campaign_name || "Campaña"}</td>
                  <td><span className="lead-recovery-typification">{lead.latest_typification_name || "Sin gestión registrada"}</span></td>
                  <td>{lead.assigned_advisor_name || "Sin asignar"}</td>
                  <td>{new Intl.DateTimeFormat("es-PE", { dateStyle: "medium" }).format(new Date(lead.created_at))}</td>
                </tr>
              ))}
              {!leads.items.length && <tr><td colSpan={5}>No hay leads recuperables para auditar.</td></tr>}
            </tbody>
          </table>
        </div>
        <Pagination data={leads} onPageChange={(page) => void load(page)} />
      </DataPanel>
    </>
  );
}
