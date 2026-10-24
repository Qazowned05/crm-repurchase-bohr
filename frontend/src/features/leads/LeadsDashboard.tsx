import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader } from "../../components/PageHeader";
import { StatCard } from "../../components/StatCard";
import { api } from "../../services/api";
import type { LeadMetrics } from "../../services/types";

function monthPeriod() {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  return { start_date: `${year}-${month}-01`, end_date: `${year}-${month}-${String(today.getDate()).padStart(2, "0")}` };
}
function currency(value: string) {
  return new Intl.NumberFormat("es-PE", { style: "currency", currency: "PEN" }).format(Number(value));
}
function percent(value: number) {
  return new Intl.NumberFormat("es-PE", { style: "percent", maximumFractionDigits: 1 }).format(value);
}

export function LeadsDashboard() {
  const [period, setPeriod] = useState(monthPeriod);
  const [metrics, setMetrics] = useState<LeadMetrics | null>(null);
  const [error, setError] = useState("");
  const load = (active = period) => api<LeadMetrics>(`/reports/leads-metrics?${new URLSearchParams(active)}`).then(setMetrics);
  useEffect(() => { load().catch(() => setError("No fue posible cargar las métricas de leads.")); }, []);
  return <>
    <PageHeader eyebrow="SUPERVISIÓN" title="Resumen de Leads" description="Mide la captación, gestión y conversión comercial del equipo." meta={<form className="dashboard-period" onSubmit={(event) => { event.preventDefault(); load().catch(() => setError("No fue posible actualizar las métricas.")); }}><label>Desde<input type="date" value={period.start_date} onChange={(event) => setPeriod((value) => ({ ...value, start_date: event.target.value }))} /></label><label>Hasta<input type="date" value={period.end_date} onChange={(event) => setPeriod((value) => ({ ...value, end_date: event.target.value }))} /></label><button>Aplicar</button></form>} />
    {error && <p className="form-error">{error}</p>}
    <section className="stats supervisor-stats">
      <StatCard label="Tasa de conversión" value={metrics ? percent(metrics.conversion_rate) : "-"} accent="green" icon="check" />
      <StatCard label="Recuperables" value={metrics ? `${metrics.recoverable_leads} · ${percent(metrics.recoverable_rate)}` : "-"} accent="orange" icon="refresh" />
      <StatCard label="Facturación Leads" value={metrics ? currency(metrics.lead_revenue) : "-"} accent="green" icon="revenue" />
      <StatCard label="Ticket promedio" value={metrics ? currency(metrics.average_ticket) : "-"} icon="ticket" />
    </section>
    <section className="dashboard-grid supervisor-dashboard-grid leads-dashboard-grid">
      <article className="panel"><h2>Captación y conversión diaria</h2>{metrics?.daily.length ? <div className="product-chart"><ResponsiveContainer width="100%" height={300}><BarChart data={metrics.daily}><CartesianGrid stroke="#dce5ec" vertical={false} /><XAxis dataKey="date" tick={{ fill: "#526b7d", fontSize: 11 }} /><YAxis allowDecimals={false} /><Tooltip /><Legend /><Bar dataKey="leads" name="Captados" fill="#176b87" radius={[4, 4, 0, 0]} /><Bar dataKey="effective" name="Efectivos" fill="#2e9278" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div> : <p>Sin leads en el periodo.</p>}</article>
      <article className="panel"><h2>Estado del pipeline actual</h2><div className="lead-pipeline-summary"><div><span>Pendientes</span><b>{metrics?.pending_leads ?? 0}</b></div><div><span>Agendados</span><b>{metrics?.scheduled_leads ?? 0}</b></div><div><span>Recuperables</span><b>{metrics?.recoverable_leads ?? 0}</b></div></div></article>
      <article className="panel"><h2>Resultado por campaña</h2>{metrics?.campaigns.length ? <div className="table-wrap"><table><thead><tr><th>Campaña</th><th>Leads</th><th>Efectivos</th><th>Recuperables</th><th>Conversión</th></tr></thead><tbody>{metrics.campaigns.map((campaign) => <tr key={campaign.campaign_id}><td><span className="campaign-color-swatch" style={{ backgroundColor: campaign.campaign_color }} /> <b>{campaign.campaign_name}</b></td><td>{campaign.leads}</td><td>{campaign.effective}</td><td>{campaign.recoverable}</td><td>{percent(campaign.leads ? campaign.effective / campaign.leads : 0)}</td></tr>)}</tbody></table></div> : <p>Sin campañas en el periodo.</p>}</article>
      <article className="panel"><h2>Rendimiento por asesor</h2>{metrics?.advisors.length ? <div className="table-wrap"><table><thead><tr><th>Asesor</th><th>Leads</th><th>Efectivos</th><th>Conversión</th><th>Ventas</th><th>Facturación</th></tr></thead><tbody>{metrics.advisors.map((advisor) => <tr key={advisor.advisor_id}><td><b>{advisor.advisor_name}</b></td><td>{advisor.leads}</td><td>{advisor.effective}</td><td>{percent(advisor.leads ? advisor.effective / advisor.leads : 0)}</td><td>{advisor.sales}</td><td>{currency(advisor.revenue)}</td></tr>)}</tbody></table></div> : <p>Sin actividad en el periodo.</p>}</article>
    </section>
  </>;
}
