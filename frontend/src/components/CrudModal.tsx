import { Modal } from "./Modal";
export type Field = {
  name: string;
  label: string;
  type?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
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
  return (
    <Modal title={title} onClose={onClose}>
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const data: Record<string, unknown> = Object.fromEntries(new FormData(e.currentTarget));
          fields
            .filter((f) => f.type === "checkbox")
            .forEach(
              (f) =>
                (data[f.name] = (
                  e.currentTarget.elements.namedItem(f.name) as HTMLInputElement
                ).checked),
            );
          fields
            .filter((f) => !f.required && f.type !== "checkbox" && data[f.name] === "")
            .forEach((f) => delete data[f.name]);
          await onSave(data);
          onClose();
        }}
      >
        <div className="form-grid">
          {fields.map((f) => (
            <label key={f.name}>
              {f.label}
              {f.options ? (
                <select
                  name={f.name}
                  defaultValue={String(initial[f.name] ?? "")}
                  required={f.required}
                >
                  {f.options.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              ) : f.type === "checkbox" ? (
                <input name={f.name} type="checkbox" defaultChecked={Boolean(initial[f.name])} />
              ) : (
                <input
                  name={f.name}
                  type={f.type || "text"}
                  defaultValue={String(initial[f.name] ?? "")}
                  required={f.required}
                />
              )}
            </label>
          ))}
        </div>
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button>Guardar</button>
        </footer>
      </form>
    </Modal>
  );
}
