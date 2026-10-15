import { useEffect, useState } from "react";
import { api } from "../services/api";
import type { Customer, LocationDepartment, Role, User } from "../services/types";
import { Modal } from "./Modal";

type CustomerPayload = Record<string, string | undefined>;

export function CustomerModal({
  customer,
  role,
  title,
  onClose,
  onSave,
}: {
  customer?: Customer | null;
  role: Role;
  title: string;
  onClose: () => void;
  onSave: (data: CustomerPayload) => Promise<void>;
}) {
  const [locations, setLocations] = useState<LocationDepartment[]>([]);
  const [advisors, setAdvisors] = useState<User[]>([]);
  const [responsibleAdvisorId, setResponsibleAdvisorId] = useState(
    customer?.responsible_advisor_id || "",
  );
  const [departmentCode, setDepartmentCode] = useState("");
  const [provinceCode, setProvinceCode] = useState("");
  const [ubigeo, setUbigeo] = useState(customer?.ubigeo || "");
  const [customerType, setCustomerType] = useState<"PERSONA" | "EMPRESA">(
    customer?.customer_type || "PERSONA",
  );
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const requestClose = () => {
    if (!dirty || window.confirm("Hay cambios sin guardar. ¿Deseas descartarlos?")) onClose();
  };

  useEffect(() => {
    api<LocationDepartment[]>("/customers/locations")
      .then((rows) => {
        setLocations(rows);
        if (!customer?.ubigeo) return;
        const department = rows.find((row) =>
          row.provinces.some((province) =>
            province.districts.some((district) => district.code === customer.ubigeo),
          ),
        );
        const province = department?.provinces.find((row) =>
          row.districts.some((district) => district.code === customer.ubigeo),
        );
        setDepartmentCode(department?.code || "");
        setProvinceCode(province?.code || "");
      })
      .catch(() => setError("No fue posible cargar el catálogo oficial de ubicaciones."));
    if (role !== "ASESOR") {
      api<User[]>("/users/advisors")
        .then(setAdvisors)
        .catch(() => setError("No fue posible cargar los asesores activos."));
    }
  }, [customer?.ubigeo, role]);

  const department = locations.find((row) => row.code === departmentCode);
  const province = department?.provinces.find((row) => row.code === provinceCode);
  const district = province?.districts.find((row) => row.code === ubigeo);
  const isCompany = customerType === "EMPRESA";

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    const form = new FormData(event.currentTarget);
    try {
      await onSave({
        ...(customer ? {} : { dni: String(form.get("dni") || "") }),
        customer_type: customerType,
        business_name: isCompany ? String(form.get("business_name") || "") : undefined,
        first_names: isCompany ? undefined : String(form.get("first_names") || ""),
        last_names: isCompany ? undefined : String(form.get("last_names") || ""),
        phone: String(form.get("phone") || ""),
        email: String(form.get("email") || "") || undefined,
        condition: String(form.get("condition") || "") || undefined,
        birth_date: isCompany ? undefined : String(form.get("birth_date") || "") || undefined,
        department: department?.name,
        province: province?.name,
        district: district?.name,
        ubigeo,
        ...(role !== "ASESOR" ? { responsible_advisor_id: responsibleAdvisorId } : {}),
      });
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible guardar el cliente.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal title={title} onClose={requestClose}>
      <form onSubmit={submit} onChange={() => setDirty(true)}>
        <div className="form-grid">
          <label className={customer ? "field-readonly" : ""}>
            Tipo de cliente
            <select
              value={customerType}
              disabled={Boolean(customer)}
              onChange={(event) => setCustomerType(event.target.value as "PERSONA" | "EMPRESA")}
            >
              <option value="PERSONA">Persona</option>
              <option value="EMPRESA">Empresa</option>
            </select>
          </label>
          <label className={customer ? "field-readonly" : ""}>
            {isCompany ? "RUC" : "DNI"}
            <input
              name="dni"
              defaultValue={customer?.dni || ""}
              required
              minLength={isCompany ? 11 : 6}
              maxLength={isCompany ? 11 : 20}
              pattern={isCompany ? "[0-9]{11}" : "[A-Za-z0-9]+"}
              disabled={Boolean(customer)}
            />
            {customer && <small>El documento no puede modificarse.</small>}
          </label>
          {isCompany ? (
            <label className="notes">
              Razón social
              <input
                name="business_name"
                defaultValue={customer?.business_name || ""}
                required
                minLength={2}
                maxLength={255}
              />
            </label>
          ) : (
            <>
              <label>
                Nombres
                <input
                  name="first_names"
                  defaultValue={customer?.first_names || ""}
                  required
                  minLength={2}
                  maxLength={120}
                />
              </label>
              <label>
                Apellidos
                <input
                  name="last_names"
                  defaultValue={customer?.last_names || ""}
                  required
                  minLength={2}
                  maxLength={120}
                />
              </label>
            </>
          )}
          <label>
            Teléfono
            <input
              name="phone"
              defaultValue={customer?.phone || ""}
              required
              minLength={6}
              maxLength={30}
            />
          </label>
          <label>
            Correo
            <input name="email" type="email" defaultValue={customer?.email || ""} />
          </label>
          {!isCompany && (
            <label>
              Fecha de nacimiento
              <input
                name="birth_date"
                type="date"
                max={new Date().toISOString().slice(0, 10)}
                defaultValue={customer?.birth_date || ""}
              />
            </label>
          )}
          {role !== "ASESOR" && (
            <label>
              Asesor responsable
              <select
                value={responsibleAdvisorId}
                required
                disabled={!advisors.length}
                onChange={(event) => setResponsibleAdvisorId(event.target.value)}
              >
                <option value="">Selecciona un asesor</option>
                {advisors.map((advisor) => (
                  <option key={advisor.id} value={advisor.id}>
                    {advisor.full_name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="notes">
            Enfermedad o condición
            <textarea name="condition" defaultValue={customer?.condition || ""} maxLength={500} />
          </label>
          <label>
            Departamento
            <select
              value={departmentCode}
              required
              disabled={!locations.length}
              onChange={(event) => {
                setDepartmentCode(event.target.value);
                setProvinceCode("");
                setUbigeo("");
              }}
            >
              <option value="">Selecciona un departamento</option>
              {locations.map((row) => (
                <option key={row.code} value={row.code}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Provincia
            <select
              value={provinceCode}
              required
              disabled={!department}
              onChange={(event) => {
                setProvinceCode(event.target.value);
                setUbigeo("");
              }}
            >
              <option value="">Selecciona una provincia</option>
              {department?.provinces.map((row) => (
                <option key={row.code} value={row.code}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Distrito
            <select
              value={ubigeo}
              required
              disabled={!province}
              onChange={(event) => setUbigeo(event.target.value)}
            >
              <option value="">Selecciona un distrito</option>
              {province?.districts.map((row) => (
                <option key={row.code} value={row.code}>
                  {row.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <footer>
          <button type="button" className="secondary" onClick={requestClose}>
            Cancelar
          </button>
          <button disabled={saving || !locations.length}>
            {saving ? "Guardando..." : "Guardar"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
