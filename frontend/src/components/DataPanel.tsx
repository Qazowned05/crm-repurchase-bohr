import type { ReactNode } from "react";

export function DataPanel({
  title,
  description,
  metric,
  actions,
  children,
  className = "",
}: {
  title: string;
  description?: ReactNode;
  metric?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel data-panel ${className}`.trim()}>
      <div className="panel-heading data-panel-heading">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {(metric || actions) && (
          <div className="data-panel-actions">
            {metric}
            {actions}
          </div>
        )}
      </div>
      {children}
    </section>
  );
}
