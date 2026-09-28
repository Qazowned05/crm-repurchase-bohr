import type { Paged } from "../services/types";

export const PAGE_SIZE = 25;

export function isPaged<T>(value: Paged<T> | T[]): value is Paged<T> {
  return !Array.isArray(value);
}

export function asPaged<T>(value: Paged<T> | T[], page = 1, pageSize = PAGE_SIZE): Paged<T> {
  return isPaged(value)
    ? value
    : { items: value, page, page_size: pageSize, total: value.length, pages: value.length ? 1 : 0 };
}

export function Pagination<T>({ data, onPageChange }: { data: Paged<T>; onPageChange: (page: number) => void }) {
  if (data.pages <= 1) return null;
  return (
    <nav className="pagination" aria-label="Paginación">
      <span>
        {data.total} registros · página {data.page} de {data.pages}
      </span>
      <button className="secondary" disabled={data.page === 1} onClick={() => onPageChange(data.page - 1)}>
        Anterior
      </button>
      <button className="secondary" disabled={data.page >= data.pages} onClick={() => onPageChange(data.page + 1)}>
        Siguiente
      </button>
    </nav>
  );
}
