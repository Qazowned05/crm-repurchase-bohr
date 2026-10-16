import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  meta,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: ReactNode;
  meta?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        <p className="eyebrow">{eyebrow}</p>
        <h2>{title}</h2>
        {description && <div className="page-header-description">{description}</div>}
      </div>
      {(meta || actions) && (
        <div className="page-header-side">
          {meta}
          {actions && <div className="page-header-actions">{actions}</div>}
        </div>
      )}
    </header>
  );
}
