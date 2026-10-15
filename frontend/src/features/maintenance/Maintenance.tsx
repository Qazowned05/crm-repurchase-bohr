import { useEffect, useState } from "react";
import { CrudModal } from "../../components/CrudModal";
import { CustomerModal } from "../../components/CustomerModal";
import { ConfirmModal, Modal } from "../../components/Modal";
import { api, download, listAll } from "../../services/api";
import { PAGE_SIZE, Pagination, asPaged } from "../../components/Pagination";
import type {
  CatalogItem,
  Customer,
  Product,
  ProductRepurchaseRule,
  Paged,
  User,
} from "../../services/types";
type Kind = "customers" | "products" | "users";
type MaintenanceFilters = Record<string, string>;
const emptyFilters = (kind: Kind): MaintenanceFilters =>
  kind === "customers"
    ? { q: "", document: "", phone: "", advisor_id: "", customer_type: "" }
    : kind === "products"
      ? { q: "", brand_id: "", category_id: "", is_active: "" }
      : {};
const definitions = {
  customers: {
    title: "Clientes",
    fields: [
      {
        name: "dni",
        label: "DNI",
        required: true,
        minLength: 6,
        maxLength: 20,
        pattern: "[A-Za-z0-9]+",
      },
      { name: "first_names", label: "Nombres", required: true, minLength: 2, maxLength: 120 },
      { name: "last_names", label: "Apellidos", required: true, minLength: 2, maxLength: 120 },
      { name: "phone", label: "Teléfono", required: true, minLength: 6, maxLength: 30 },
      { name: "email", label: "Correo", type: "email" },
      { name: "condition", label: "Enfermedad o condición" },
    ],
  },
  products: { title: "Productos", fields: [] },
  users: {
    title: "Usuarios",
    fields: [
      { name: "email", label: "Correo", type: "email", required: true },
      { name: "full_name", label: "Nombre completo", required: true, minLength: 2 },
      {
        name: "password",
        label: "Contraseña",
        type: "password",
        required: true,
        minLength: 8,
        maxLength: 128,
        helpText: "Mínimo 8 caracteres.",
      },
      {
        name: "role",
        label: "Rol",
        required: true,
        options: [
          { value: "ASESOR", label: "Asesor" },
          { value: "SUPERVISOR", label: "Supervisor" },
          { value: "ADMIN", label: "Administrador" },
        ],
      },
    ],
  },
} as const;
export function Maintenance({ kind, user }: { kind: Kind; user: User }) {
  const [data, setData] = useState<Paged<Customer | Product | User>>({
    items: [],
    page: 1,
    page_size: PAGE_SIZE,
    total: 0,
    pages: 0,
  });
  const [editing, setEditing] = useState<Customer | Product | User | null | undefined>(undefined);
  const [creatingProduct, setCreatingProduct] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [catalog, setCatalog] = useState<"brands" | "product-categories" | null>(null);
  const [filters, setFilters] = useState<MaintenanceFilters>(() => emptyFilters(kind));
  const [advisors, setAdvisors] = useState<User[]>([]);
  const [brands, setBrands] = useState<CatalogItem[]>([]);
  const [categories, setCategories] = useState<CatalogItem[]>([]);
  const d = definitions[kind];
  const load = (page = data.page, activeFilters = filters) => {
    const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (kind === "products") query.set("include_inactive", "true");
    Object.entries(activeFilters).forEach(([key, value]) => value && query.set(key, value));
    return api<Paged<Customer | Product | User> | Array<Customer | Product | User>>(
      `/${kind}?${query}`,
    ).then((value) => setData(asPaged(value, page)));
  };
  useEffect(() => {
    const nextFilters = emptyFilters(kind);
    setFilters(nextFilters);
    load(1, nextFilters).catch(() =>
      setData({ items: [], page: 1, page_size: PAGE_SIZE, total: 0, pages: 0 }),
    );
    if (kind === "customers" && user.role !== "ASESOR") {
      api<User[]>("/users/advisors")
        .then(setAdvisors)
        .catch(() => setAdvisors([]));
    }
    if (kind === "products") {
      Promise.all([listAll<CatalogItem>("/brands"), listAll<CatalogItem>("/product-categories")])
        .then(([brandRows, categoryRows]) => {
          setBrands(brandRows);
          setCategories(categoryRows);
        })
        .catch(() => {
          setBrands([]);
          setCategories([]);
        });
    }
  }, [kind]);
  const rows = data.items;
  const headers =
    kind === "customers"
      ? ["Cliente", "Documento", "Número", "Estado"]
      : ["Nombre", "Referencia", "Detalle", "Estado / rol"];
  const display = (r: Customer | Product | User) =>
    "full_name" in r
      ? [r.full_name, r.email, r.role, r.is_active ? "Activo" : "Inactivo"]
      : "dni" in r
        ? [r.business_name || `${r.first_names} ${r.last_names}`.trim(), r.dni, r.phone, r.status]
        : [
            r.name,
            r.code,
            `${r.brand_name} / ${r.category_name}`,
            r.is_active ? "Activo" : "Inactivo",
          ];
  const canWrite = kind !== "users" || user.role === "ADMIN";
  const showActions = kind !== "users" || canWrite;
  const exportRows = async () => {
    const query = new URLSearchParams();
    if (kind === "products") query.set("include_inactive", "true");
    Object.entries(filters).forEach(([key, value]) => value && query.set(key, value));
    await download(`/${kind}/export.xlsx?${query}`, `${kind}.xlsx`);
  };
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">MANTENIMIENTO</p>
          <h1>{d.title}</h1>
          {kind === "products" && (
            <p>Administra productos, marcas, categorías y sus reglas vigentes de recompra.</p>
          )}
        </div>
        {canWrite && (
          <div className="product-page-actions">
            {kind === "products" && (
              <>
                <button className="secondary" onClick={() => setCatalog("brands")}>
                  Marcas
                </button>
                <button className="secondary" onClick={() => setCatalog("product-categories")}>
                  Categorías
                </button>
              </>
            )}
            {(kind === "customers" || kind === "products") && (
              <button className="secondary" onClick={() => exportRows().catch(() => {})}>
                Exportar Excel
              </button>
            )}
            <button
              onClick={() => (kind === "products" ? setCreatingProduct(true) : setEditing(null))}
            >
              Nuevo
            </button>
          </div>
        )}
      </div>
      <section className="panel">
        {kind === "customers" && (
          <form
            className="maintenance-filters"
            onSubmit={(event) => {
              event.preventDefault();
              load(1).catch(() => {});
            }}
          >
            <label>
              Buscar cliente
              <input
                value={filters.q}
                placeholder="Nombre o razón social"
                onChange={(event) => setFilters({ ...filters, q: event.target.value })}
              />
            </label>
            <label>
              DNI o RUC
              <input
                value={filters.document}
                placeholder="Número de documento"
                onChange={(event) => setFilters({ ...filters, document: event.target.value })}
              />
            </label>
            <label>
              Teléfono
              <input
                value={filters.phone}
                placeholder="Número telefónico"
                onChange={(event) => setFilters({ ...filters, phone: event.target.value })}
              />
            </label>
            <label>
              Tipo
              <select
                value={filters.customer_type}
                onChange={(event) => setFilters({ ...filters, customer_type: event.target.value })}
              >
                <option value="">Todos</option>
                <option value="PERSONA">Persona</option>
                <option value="EMPRESA">Empresa</option>
              </select>
            </label>
            {user.role !== "ASESOR" && (
              <label>
                Asesor asignado
                <select
                  value={filters.advisor_id}
                  onChange={(event) => setFilters({ ...filters, advisor_id: event.target.value })}
                >
                  <option value="">Todos</option>
                  {advisors.map((advisor) => (
                    <option key={advisor.id} value={advisor.id}>
                      {advisor.full_name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <div className="maintenance-filter-actions">
              <button>Filtrar</button>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  const nextFilters = emptyFilters(kind);
                  setFilters(nextFilters);
                  load(1, nextFilters).catch(() => {});
                }}
              >
                Limpiar
              </button>
            </div>
          </form>
        )}
        {kind === "products" && (
          <form
            className="maintenance-filters"
            onSubmit={(event) => {
              event.preventDefault();
              load(1).catch(() => {});
            }}
          >
            <label>
              Buscar producto
              <input
                value={filters.q}
                placeholder="Nombre o código"
                onChange={(event) => setFilters({ ...filters, q: event.target.value })}
              />
            </label>
            <label>
              Marca
              <select
                value={filters.brand_id}
                onChange={(event) => setFilters({ ...filters, brand_id: event.target.value })}
              >
                <option value="">Todas</option>
                {brands.map((brand) => (
                  <option key={brand.id} value={brand.id}>
                    {brand.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Categoría
              <select
                value={filters.category_id}
                onChange={(event) => setFilters({ ...filters, category_id: event.target.value })}
              >
                <option value="">Todas</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Estado
              <select
                value={filters.is_active}
                onChange={(event) => setFilters({ ...filters, is_active: event.target.value })}
              >
                <option value="">Todos</option>
                <option value="true">Activo</option>
                <option value="false">Inactivo</option>
              </select>
            </label>
            <div className="maintenance-filter-actions">
              <button>Filtrar</button>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  const nextFilters = emptyFilters(kind);
                  setFilters(nextFilters);
                  load(1, nextFilters).catch(() => {});
                }}
              >
                Limpiar
              </button>
            </div>
          </form>
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {headers.map((header) => (
                  <th key={header}>{header}</th>
                ))}
                {showActions && <th />}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  {display(r).map((v, i) => (
                    <td key={i}>{v}</td>
                  ))}
                  {showActions && (
                    <td className="maintenance-actions">
                      {kind === "customers" && (
                        <button className="link" onClick={() => setSelectedCustomer(r as Customer)}>
                          Ver
                        </button>
                      )}
                      {kind === "products" && (
                        <button className="link" onClick={() => setSelectedProduct(r as Product)}>
                          Ver
                        </button>
                      )}
                      {canWrite && (
                        <button
                          className="link"
                          onClick={() =>
                            kind === "products" ? setEditingProduct(r as Product) : setEditing(r)
                          }
                        >
                          Editar
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
              {!rows.length && (
                <tr>
                  <td colSpan={5}>No hay registros disponibles.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <Pagination data={data} onPageChange={(page) => load(page).catch(() => {})} />
      </section>
      {editing !== undefined && kind === "customers" && (
        <CustomerModal
          title={editing ? "Editar cliente" : "Nuevo cliente"}
          customer={(editing as Customer | null) || undefined}
          role={user.role}
          onClose={() => setEditing(undefined)}
          onSave={async (data) => {
            await api(`/customers${editing ? `/${editing.id}` : ""}`, {
              method: editing ? "PATCH" : "POST",
              body: JSON.stringify(data),
            });
            await load();
          }}
        />
      )}
      {selectedCustomer && (
        <CustomerDetailsModal
          customer={selectedCustomer}
          advisor={advisors.find(
            (advisor) => advisor.id === selectedCustomer.responsible_advisor_id,
          )}
          onClose={() => setSelectedCustomer(null)}
        />
      )}
      {editing !== undefined && kind === "users" && (
        <CrudModal
          title={editing ? `Editar ${kind.slice(0, -1)}` : `Nuevo ${kind.slice(0, -1)}`}
          fields={
            d.fields.map((field) => {
              if (editing && kind === "users" && field.name === "email")
                return { ...field, disabled: true, helpText: "El correo no puede modificarse." };
              if (editing && kind === "users" && field.name === "password")
                return {
                  ...field,
                  required: false,
                  helpText: "Déjalo vacío para conservar la contraseña actual.",
                };
              return field;
            }) as never
          }
          initial={editing || {}}
          onClose={() => setEditing(undefined)}
          onSave={async (data) => {
            if (editing && kind === "users") {
              delete data.email;
              if (!data.password) delete data.password;
            }
            await api(`/${kind}${editing ? `/${editing.id}` : ""}`, {
              method: editing ? "PATCH" : "POST",
              body: JSON.stringify(data),
            });
            await load();
          }}
        />
      )}
      {creatingProduct && (
        <ProductCreateModal
          onClose={() => setCreatingProduct(false)}
          onCreated={async () => {
            await load();
            setCreatingProduct(false);
          }}
        />
      )}
      {editingProduct && (
        <ProductEditModal
          product={editingProduct}
          onClose={() => setEditingProduct(null)}
          onSaved={async () => {
            await load();
            setEditingProduct(null);
          }}
        />
      )}
      {selectedProduct && (
        <ProductDetailsModal
          product={selectedProduct}
          canWrite={canWrite}
          onClose={() => setSelectedProduct(null)}
        />
      )}
      {catalog && (
        <CatalogModal
          endpoint={catalog}
          title={catalog === "brands" ? "Marcas" : "Categorías"}
          onClose={() => setCatalog(null)}
        />
      )}
    </>
  );
}

const today = () => new Date().toLocaleDateString("en-CA");

function RuleFields() {
  return (
    <div className="form-grid rule-fields">
      <label>
        Duración de recompra (días)
        <input name="duration_days" type="number" min="1" max="730" required />
      </label>
      <label>
        Días de alerta
        <input name="alert_days" placeholder="Ej. 30, 15, 7" required />
        <small>Sepáralos por comas. Deben ser menores que la duración.</small>
      </label>
      <label>
        Vigente desde
        <input name="effective_from" type="date" defaultValue={today()} required />
      </label>
    </div>
  );
}

function rulePayload(form: HTMLFormElement) {
  const data = Object.fromEntries(new FormData(form));
  const alertDays = String(data.alert_days)
    .split(",")
    .map((day) => Number(day.trim()));
  if (
    !alertDays.length ||
    alertDays.some((day) => !Number.isInteger(day) || day <= 0) ||
    new Set(alertDays).size !== alertDays.length
  )
    throw new Error("Los días de alerta deben ser números enteros positivos y no repetidos.");
  const duration = Number(data.duration_days);
  if (!Number.isInteger(duration) || duration < 1 || alertDays.some((day) => day >= duration))
    throw new Error("Cada día de alerta debe ser menor que la duración de recompra.");
  return {
    duration_days: duration,
    alert_days: alertDays,
    effective_from: String(data.effective_from),
  };
}

function ProductCreateModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [brands, setBrands] = useState<CatalogItem[]>([]);
  const [categories, setCategories] = useState<CatalogItem[]>([]);
  useEffect(() => {
    Promise.all([listAll<CatalogItem>("/brands"), listAll<CatalogItem>("/product-categories")])
      .then(([brandRows, categoryRows]) => {
        setBrands(brandRows);
        setCategories(categoryRows);
      })
      .catch(() => setError("No fue posible cargar marcas y categorías."));
  }, []);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    const form = event.currentTarget;
    try {
      const rule = rulePayload(form);
      const data = Object.fromEntries(new FormData(form));
      const product = await api<Product>("/products", {
        method: "POST",
        body: JSON.stringify({
          code: data.code,
          name: data.name,
          brand_id: data.brand_id,
          category_id: data.category_id,
          unit_price: data.unit_price,
        }),
      });
      try {
        await api(`/products/${product.id}/rules`, { method: "POST", body: JSON.stringify(rule) });
      } catch (reason) {
        throw new Error(
          `El producto ${product.code} fue creado, pero su regla no pudo registrarse. No podrá venderse hasta que se cree una regla vigente. ${reason instanceof Error ? reason.message : ""}`,
        );
      }
      await onCreated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible crear el producto.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal title="Nuevo producto y regla inicial" onClose={onClose}>
      <form onSubmit={submit}>
        <p className="modal-intro">
          Todo producto requiere una regla efectiva para poder registrarse en ventas.
        </p>
        <div className="form-grid">
          <label>
            Código
            <input name="code" required minLength={2} />
          </label>
          <label>
            Nombre
            <input name="name" required minLength={2} />
          </label>
          <label>
            Marca
            <select name="brand_id" required defaultValue="">
              <option value="" disabled>
                Selecciona una marca
              </option>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Categoría
            <select name="category_id" required defaultValue="">
              <option value="" disabled>
                Selecciona una categoría
              </option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Precio unitario
            <input name="unit_price" type="number" min="0.01" step="0.01" required />
          </label>
        </div>
        <h3 className="modal-section-title">Regla inicial de recompra</h3>
        <RuleFields />
        {error && <p className="form-error">{error}</p>}
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button disabled={saving || !brands.length || !categories.length}>
            {saving ? "Guardando..." : "Crear producto"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function ProductEditModal({
  product,
  onClose,
  onSaved,
}: {
  product: Product;
  onClose: () => void;
  onSaved: () => Promise<void>;
}) {
  const [brands, setBrands] = useState<CatalogItem[]>([]);
  const [categories, setCategories] = useState<CatalogItem[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    Promise.all([listAll<CatalogItem>("/brands"), listAll<CatalogItem>("/product-categories")])
      .then(([brandRows, categoryRows]) => {
        setBrands(brandRows);
        setCategories(categoryRows);
      })
      .catch(() => setError("No fue posible cargar marcas y categorías."));
  }, []);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    const data = Object.fromEntries(new FormData(event.currentTarget));
    try {
      await api(`/products/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: data.name,
          brand_id: data.brand_id,
          category_id: data.category_id,
          unit_price: data.unit_price,
          is_active: data.is_active === "on",
        }),
      });
      await onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible actualizar el producto.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal title={`Editar ${product.name}`} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="form-grid">
          <label>
            Código
            <input defaultValue={product.code} disabled />
          </label>
          <label>
            Nombre
            <input name="name" required minLength={2} defaultValue={product.name} />
          </label>
          <label>
            Marca
            <select name="brand_id" required defaultValue={product.brand_id}>
              {brands.map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Categoría
            <select name="category_id" required defaultValue={product.category_id}>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Precio unitario
            <input
              name="unit_price"
              type="number"
              min="0.01"
              step="0.01"
              required
              defaultValue={product.unit_price}
            />
          </label>
          <label>
            Activo
            <input name="is_active" type="checkbox" defaultChecked={product.is_active} />
          </label>
        </div>
        {error && <p className="form-error">{error}</p>}
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button disabled={saving || !brands.length || !categories.length}>
            {saving ? "Guardando..." : "Guardar"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}

function CatalogModal({
  endpoint,
  title,
  onClose,
}: {
  endpoint: "brands" | "product-categories";
  title: string;
  onClose: () => void;
}) {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [editing, setEditing] = useState<CatalogItem | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<CatalogItem | null>(null);
  const [error, setError] = useState("");
  const load = () =>
    listAll<CatalogItem>(`/${endpoint}?include_inactive=true`)
      .then(setItems)
      .catch(() => setError(`No fue posible cargar ${title.toLowerCase()}.`));
  useEffect(() => {
    load();
  }, [endpoint]);
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const name = String(new FormData(event.currentTarget).get("name") || "");
    try {
      await api(`/${endpoint}${editing ? `/${editing.id}` : ""}`, {
        method: editing ? "PATCH" : "POST",
        body: JSON.stringify({ name }),
      });
      await load();
      setEditing(null);
      setCreating(false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible guardar el registro.");
    }
  }
  return (
    <>
      <Modal title={title} onClose={onClose}>
        {creating || editing ? (
          <form onSubmit={save}>
            <label>
              Nombre
              <input
                name="name"
                required
                minLength={1}
                maxLength={120}
                defaultValue={editing?.name || ""}
                autoFocus
              />
            </label>
            {error && <p className="form-error">{error}</p>}
            <footer>
              <button
                type="button"
                className="secondary"
                onClick={() => {
                  setEditing(null);
                  setCreating(false);
                }}
              >
                Cancelar
              </button>
              <button>Guardar</button>
            </footer>
          </form>
        ) : (
          <>
            <div className="modal-heading">
              <div>
                <p>Administra las opciones disponibles al registrar productos.</p>
              </div>
              <button onClick={() => setCreating(true)}>
                Nueva {title.slice(0, -1).toLowerCase()}
              </button>
            </div>
            {error && <p className="form-error">{error}</p>}
            <div className="catalog-list">
              {items.map((item) => (
                <div key={item.id}>
                  <span>{item.name}</span>
                  <span className={item.is_active ? "status-active" : "status-inactive"}>
                    {item.is_active ? "Activo" : "Inactivo"}
                  </span>
                  <button className="link" onClick={() => setEditing(item)}>
                    Editar
                  </button>
                  <button
                    className="link"
                    onClick={async () => {
                      try {
                        await api(`/${endpoint}/${item.id}`, {
                          method: "PATCH",
                          body: JSON.stringify({ is_active: !item.is_active }),
                        });
                        await load();
                      } catch (reason) {
                        setError(
                          reason instanceof Error
                            ? reason.message
                            : "No fue posible cambiar el estado.",
                        );
                      }
                    }}
                  >
                    {item.is_active ? "Desactivar" : "Activar"}
                  </button>
                  <button className="link danger-link" onClick={() => setDeleting(item)}>
                    Eliminar
                  </button>
                </div>
              ))}
              {!items.length && <p className="empty-rules">No hay registros disponibles.</p>}
            </div>
            <footer>
              <button type="button" className="secondary" onClick={onClose}>
                Cerrar
              </button>
            </footer>
          </>
        )}
      </Modal>
      {deleting && (
        <ConfirmModal
          title={`Eliminar ${title.slice(0, -1).toLowerCase()}`}
          message={`¿Eliminar ${deleting.name}? Esta acción no se puede deshacer.`}
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            try {
              await api(`/${endpoint}/${deleting.id}`, { method: "DELETE" });
              await load();
            } catch (reason) {
              setError(
                reason instanceof Error ? reason.message : "No fue posible eliminar el registro.",
              );
            }
          }}
        />
      )}
    </>
  );
}

function CustomerDetailsModal({
  customer,
  advisor,
  onClose,
}: {
  customer: Customer;
  advisor?: User;
  onClose: () => void;
}) {
  const isCompany = customer.customer_type === "EMPRESA";
  const location = [customer.district, customer.province, customer.department]
    .filter(Boolean)
    .join(", ");
  return (
    <Modal title="Ficha del cliente" onClose={onClose}>
      <div className="customer-detail-heading">
        <div>
          <p className="eyebrow">{isCompany ? "EMPRESA" : "PERSONA"}</p>
          <h3>
            {customer.business_name || `${customer.first_names} ${customer.last_names}`.trim()}
          </h3>
        </div>
        <span className={customer.status === "ACTIVO" ? "status-active" : "status-inactive"}>
          {customer.status}
        </span>
      </div>
      <dl className="customer-details">
        <div>
          <dt>{isCompany ? "RUC" : "DNI"}</dt>
          <dd>{customer.dni}</dd>
        </div>
        <div>
          <dt>Teléfono</dt>
          <dd>{customer.phone}</dd>
        </div>
        <div>
          <dt>Correo</dt>
          <dd>{customer.email || "No registrado"}</dd>
        </div>
        <div>
          <dt>Asesor asignado</dt>
          <dd>{advisor?.full_name || "Sin asignar"}</dd>
        </div>
        {!isCompany && (
          <div>
            <dt>Fecha de nacimiento</dt>
            <dd>{customer.birth_date || "No registrada"}</dd>
          </div>
        )}
        <div className="customer-details-wide">
          <dt>Ubicación</dt>
          <dd>{location || "No registrada"}</dd>
        </div>
        <div className="customer-details-wide">
          <dt>Enfermedad o condición</dt>
          <dd>{customer.condition || "No registrada"}</dd>
        </div>
      </dl>
      <footer>
        <button type="button" className="secondary" onClick={onClose}>
          Cerrar
        </button>
      </footer>
    </Modal>
  );
}

function ProductDetailsModal({
  product,
  canWrite,
  onClose,
}: {
  product: Product;
  canWrite: boolean;
  onClose: () => void;
}) {
  const [rules, setRules] = useState<ProductRepurchaseRule[]>([]);
  const [error, setError] = useState("");
  const [newRule, setNewRule] = useState(false);
  const loadRules = async () => {
    try {
      setError("");
      setRules(await api<ProductRepurchaseRule[]>(`/products/${product.id}/rules`));
    } catch {
      setError("No fue posible cargar el historial de reglas.");
    }
  };
  useEffect(() => {
    loadRules();
  }, [product.id]);
  return (
    <>
      <Modal title={`Reglas de ${product.name}`} onClose={onClose}>
        <div className="product-summary">
          <b>{product.code}</b>
          <span>{product.brand_name}</span>
          <span>{product.category_name}</span>
          <span className={product.is_active ? "status-active" : "status-inactive"}>
            {product.is_active ? "Activo" : "Inactivo"}
          </span>
        </div>
        <div className="modal-heading">
          <div>
            <h3>Historial de reglas</h3>
            <p>La regla con la fecha de vigencia más reciente aplica a cada venta.</p>
          </div>
          {canWrite && <button onClick={() => setNewRule(true)}>Nueva versión</button>}
        </div>
        {error && <p className="form-error">{error}</p>}
        <div className="rule-history">
          {rules.map((rule, index) => (
            <article key={rule.id} className="rule-card">
              <header>
                <b>{index === 0 ? "Regla más reciente" : "Versión anterior"}</b>
                <time>Vigente desde {rule.effective_from}</time>
              </header>
              <div>
                <span>{rule.duration_days} días</span>
                <span>Alertas: {rule.alert_days.join(", ")} días antes</span>
              </div>
            </article>
          ))}
          {!rules.length && !error && (
            <p className="empty-rules">
              Este producto no tiene reglas. No podrá venderse hasta registrar una.
            </p>
          )}
        </div>
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Cerrar
          </button>
        </footer>
      </Modal>
      {newRule && (
        <RuleCreateModal
          product={product}
          onClose={() => setNewRule(false)}
          onCreated={async () => {
            await loadRules();
            setNewRule(false);
          }}
        />
      )}
    </>
  );
}

function RuleCreateModal({
  product,
  onClose,
  onCreated,
}: {
  product: Product;
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      await api(`/products/${product.id}/rules`, {
        method: "POST",
        body: JSON.stringify(rulePayload(event.currentTarget)),
      });
      await onCreated();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible registrar la regla.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal title={`Nueva regla para ${product.code}`} onClose={onClose}>
      <form onSubmit={submit}>
        <p className="modal-intro">
          Esta versión conserva las reglas históricas y se aplicará desde su fecha de vigencia.
        </p>
        <RuleFields />
        {error && <p className="form-error">{error}</p>}
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button disabled={saving}>{saving ? "Guardando..." : "Crear versión"}</button>
        </footer>
      </form>
    </Modal>
  );
}
