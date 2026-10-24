import { useEffect, useState } from "react";
import { CrudModal } from "../../components/CrudModal";
import { DataPanel } from "../../components/DataPanel";
import { PageHeader } from "../../components/PageHeader";
import { api } from "../../services/api";
import type { Campaign } from "../../services/types";

export function Campaigns() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [edit, setEdit] = useState<Campaign | null | undefined>(undefined);
  const [error, setError] = useState("");
  const load = () => api<Campaign[]>("/campaigns").then(setCampaigns);
  useEffect(() => { load().catch(() => setError("No fue posible cargar las campañas.")); }, []);
  return <><PageHeader eyebrow="CONFIGURACIÓN" title="Campañas" description="Crea y desactiva las campañas disponibles para los leads." actions={<button onClick={() => setEdit(null)}>Nueva campaña</button>} />
    {error && <p className="error-message">{error}</p>}
    <DataPanel title="Campañas de leads" description={`${campaigns.length} campañas configuradas`}><div className="table-wrap"><table><thead><tr><th>Campaña</th><th>Color</th><th>Estado</th><th /></tr></thead><tbody>{campaigns.map((campaign) => <tr key={campaign.id}><td>{campaign.name}</td><td><span className="campaign-color-swatch" style={{ backgroundColor: campaign.color }} aria-label={`Color ${campaign.color}`} /> {campaign.color}</td><td><span className={`status ${campaign.is_active ? "success" : "neutral"}`}>{campaign.is_active ? "Activa" : "Inactiva"}</span></td><td><button className="link" onClick={() => setEdit(campaign)}>Editar</button></td></tr>)}{!campaigns.length && <tr><td colSpan={4}>No hay campañas configuradas.</td></tr>}</tbody></table></div></DataPanel>
    {edit !== undefined && <CrudModal title={edit ? "Editar campaña" : "Nueva campaña"} initial={edit || { is_active: true, color: "#176b87" }} fields={[{ name: "name", label: "Nombre", required: true }, { name: "color", label: "Color", type: "color", required: true }, { name: "is_active", label: "Activa", type: "checkbox" }]} onClose={() => setEdit(undefined)} onSave={async (data) => { await api(`/campaigns${edit ? `/${edit.id}` : ""}`, { method: edit ? "PATCH" : "POST", body: JSON.stringify(data) }); await load(); }} />}</>;
}
