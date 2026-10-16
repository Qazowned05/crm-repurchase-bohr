import type { ReactNode } from "react";

type MetricIcon = "calendar" | "check" | "clock" | "package" | "refresh" | "revenue" | "ticket";

function Icon({ name }: { name: MetricIcon }) {
  const paths: Record<MetricIcon, ReactNode> = {
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="2" />
        <path d="M7 3v4M17 3v4M3 10h18M8 14h3M8 18h5" />
      </>
    ),
    check: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="m8 12 2.5 2.5L16 9" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    package: (
      <>
        <path d="m4 7 8-4 8 4v10l-8 4-8-4Z" />
        <path d="m4 7 8 4 8-4M12 11v10" />
      </>
    ),
    refresh: <path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5" />,
    revenue: (
      <>
        <rect x="4" y="6" width="16" height="13" rx="2" />
        <path d="M4 10h16M8 15h3" />
      </>
    ),
    ticket: (
      <>
        <path d="M5 4h14v16H5z" />
        <path d="M8 8h8M8 12h8M8 16h4" />
      </>
    ),
  };
  return (
    <svg className="stat-icon" viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

export function StatCard({
  label,
  value,
  accent = "blue",
  icon = "ticket",
}: {
  label: string;
  value: string | number;
  accent?: string;
  icon?: MetricIcon;
}) {
  return (
    <article className={`stat ${accent}`}>
      <Icon name={icon} />
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}
