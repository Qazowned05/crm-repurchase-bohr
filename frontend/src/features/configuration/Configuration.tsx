import { useEffect, useState } from "react";
import { ConfirmModal } from "../../components/Modal";
import { CrudModal } from "../../components/CrudModal";
import { api } from "../../services/api";
import type { Typification, TypificationTree } from "../../services/types";

function flatten(
  nodes: TypificationTree[],
  depth = 0,
): Array<{ node: TypificationTree; depth: number }> {
  return nodes.flatMap((node) => [{ node, depth }, ...flatten(node.children, depth + 1)]);
}
function rules(node: Typification): string[] {
  return [
    node.requires_next_action ? "Seguimiento" : null,
    node.requires_note ? "Nota" : null,
    node.requires_close ? "Cierre" : null,
  ].filter((rule): rule is string => rule !== null);
}
function TreeNode({
  node,
  depth,
  onEdit,
  onDelete,
}: {
  node: TypificationTree;
  depth: number;
  onEdit: (node: Typification) => void;
  onDelete: (node: Typification) => void;
}) {
  const [open, setOpen] = useState(true);
  const nodeRules = rules(node);
  return (
    <li className="tree-node">
      <div className="tree-row" style={{ paddingLeft: `${20 + depth * 28}px` }}>
        <button
          className={`tree-toggle ${node.children.length ? "" : "empty"}`}
          onClick={() => setOpen((value) => !value)}
          aria-label={open ? "Contraer" : "Expandir"}
        >
          {node.children.length ? (open ? "-" : "+") : ""}
        </button>
        <div className="tree-main">
          <div>
            <b>{node.name}</b>
            <code>{node.code}</code>
          </div>
          <div className="rule-list">
            {nodeRules.length ? (
              nodeRules.map((rule) => <span key={rule}>{rule}</span>)
            ) : (
              <span className="muted">Sin reglas</span>
            )}
          </div>
        </div>
        <span className={`status ${node.is_active ? "success" : "neutral"}`}>
          {node.is_active ? "Activa" : "Inactiva"}
        </span>
        <div className="row-actions">
          <button className="link" onClick={() => onEdit(node)}>
            Editar
          </button>
          <button className="link danger-text" onClick={() => onDelete(node)}>
            Eliminar
          </button>
        </div>
      </div>
      {open && node.children.length > 0 && (
        <ul>
          {node.children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
export function Configuration() {
  const [tree, setTree] = useState<TypificationTree[]>([]);
  const [edit, setEdit] = useState<Typification | null | undefined>(undefined);
  const [remove, setRemove] = useState<Typification | null>(null);
  const [error, setError] = useState("");
  const load = () =>
    api<TypificationTree[]>("/configuration/contact-typifications/tree").then(setTree);
  useEffect(() => {
    load().catch(() => setError("No fue posible cargar la estructura de tipificaciones."));
  }, []);
  const flat = flatten(tree);
  const invalidParents = new Set(edit ? [edit.id, ...collectDescendants(edit.id, tree)] : []);
  const fields = [
    ...(!edit ? [{ name: "code", label: "Código", required: true }] : []),
    { name: "name", label: "Nombre", required: true },
    {
      name: "parent_id",
      label: "Ubicación en la jerarquía",
      options: [
        { value: "__root__", label: "Sin padre (nivel principal)" },
        ...flat
          .filter(({ node }) => !invalidParents.has(node.id))
          .map(({ node, depth }) => ({
            value: node.id,
            label: `${"  ".repeat(depth)}${node.name} (${node.code})`,
          })),
      ],
    },
    { name: "is_active", label: "Activa", type: "checkbox" },
    { name: "requires_next_action", label: "Requiere siguiente acción", type: "checkbox" },
    { name: "requires_note", label: "Requiere nota", type: "checkbox" },
    { name: "requires_close", label: "Requiere cierre", type: "checkbox" },
  ];
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">CONFIGURACIÓN</p>
          <h1>Tipificaciones de contacto</h1>
          <p>Organiza los resultados de atención en una estructura clara y reutilizable.</p>
        </div>
        <button
          onClick={() => {
            setError("");
            setEdit(null);
          }}
        >
          Nueva tipificación
        </button>
      </div>
      <section className="panel tree-panel">
        <div className="panel-heading">
          <div>
            <h2>Árbol de tipificaciones</h2>
            <p>{flat.length} tipificaciones configuradas</p>
          </div>
          <span className="legend-dot">Nivel principal</span>
        </div>
        {error && <p className="form-error">{error}</p>}
        <ul className="typification-tree">
          {tree.map((node) => (
            <TreeNode key={node.id} node={node} depth={0} onEdit={setEdit} onDelete={setRemove} />
          ))}
        </ul>
        {!tree.length && !error && (
          <div className="empty-state">
            Aún no hay tipificaciones. Crea la primera categoría para comenzar.
          </div>
        )}
      </section>
      {edit !== undefined && (
        <CrudModal
          title={edit ? "Editar tipificación" : "Nueva tipificación"}
          fields={fields}
          initial={
            edit
              ? { ...edit, parent_id: edit.parent_id || "__root__" }
              : { parent_id: "__root__", is_active: true }
          }
          onClose={() => setEdit(undefined)}
          onSave={async (data) => {
            if (data.parent_id === "__root__") data.parent_id = null;
            await api(`/configuration/contact-typifications${edit ? `/${edit.id}` : ""}`, {
              method: edit ? "PATCH" : "POST",
              body: JSON.stringify(data),
            });
            await load();
          }}
        />
      )}
      {remove && (
        <ConfirmModal
          message={`Eliminar “${remove.name}” (${remove.code}). Solo podrás eliminarla si no tiene subtipificaciones ni registros relacionados.`}
          onClose={() => setRemove(null)}
          onConfirm={async () => {
            await api(`/configuration/contact-typifications/${remove.id}`, { method: "DELETE" });
            await load();
          }}
        />
      )}
    </>
  );
}
function collectDescendants(id: string, nodes: TypificationTree[]): string[] {
  for (const node of nodes) {
    if (node.id === id) return flatten(node.children).map((item) => item.node.id);
    const found = collectDescendants(id, node.children);
    if (found.length) return found;
  }
  return [];
}
