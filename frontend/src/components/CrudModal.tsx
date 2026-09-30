import { useState } from "react";
import { Modal } from "./Modal";
export type Field = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  minLength?: number;
  maxLength?: number;
  min?: number;
  max?: number;
  step?: number;
  pattern?: string;
  disabled?: boolean;
  helpText?: string;
};
export function CrudModal({
  title,
  fields,
  initial = {},
  onClose,
  onSave,
}: {
  title: string;
  fields: Field[];
  initial?: Record<string, unknown>;
  onClose: () => void;
  onSave: (data: Record<string, unknown>) => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const requestClose = () => {
    if (!dirty || window.confirm("Hay cambios sin guardar. ¿Deseas descartarlos?")) onClose();
  };
  return (
    <Modal title={title} onClose={requestClose}>
      <form
        noValidate
        onChange={() => setDirty(true)}
        onSubmit={async (e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const invalid = form.querySelector<
            HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
          >(":invalid");
          if (invalid) {
            setError(invalid.validationMessage || `Revisa el campo ${invalid.name}.`);
            invalid.focus();
            return;
          }
          setError("");
          setSaving(true);
          const data: Record<string, unknown> = Object.fromEntries(new FormData(form));
          fields
            .filter((f) => f.type === "checkbox")
            .forEach(
              (f) => (data[f.name] = (form.elements.namedItem(f.name) as HTMLInputElement).checked),
            );
          fields
            .filter((f) => !f.required && f.type !== "checkbox" && data[f.name] === "")
            .forEach((f) => delete data[f.name]);
          try {
            await onSave(data);
            onClose();
          } catch (reason) {
            setError(
              reason instanceof Error ? reason.message : "No fue posible guardar los cambios.",
            );
          } finally {
            setSaving(false);
          }
        }}
      >
        <div className="form-grid">
          {fields.map((f) => (
            <label key={f.name} className={f.disabled ? "field-readonly" : ""}>
              <span className="field-label">{f.label}</span>
              {f.options ? (
                <select
                  name={f.name}
                  defaultValue={String(initial[f.name] ?? "")}
                  required={f.required}
                  disabled={f.disabled}
                >
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              ) : f.type === "checkbox" ? (
                <input
                  name={f.name}
                  type="checkbox"
                  defaultChecked={Boolean(initial[f.name])}
                  disabled={f.disabled}
                />
              ) : (
                <input
                  name={f.name}
                  type={f.type || "text"}
                  defaultValue={String(initial[f.name] ?? "")}
                  required={f.required}
                  minLength={f.minLength}
                  maxLength={f.maxLength}
                  min={f.min}
                  max={f.max}
                  step={f.step}
                  pattern={f.pattern}
                  disabled={f.disabled}
                />
              )}
              {f.helpText && <small>{f.helpText}</small>}
            </label>
          ))}
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
          <button disabled={saving}>{saving ? "Guardando..." : "Guardar"}</button>
        </footer>
      </form>
    </Modal>
  );
}
