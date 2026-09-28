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

export function Pagination<T>({
  data,
  onPageChange,
}: {
  data: Paged<T>;
  onPageChange: (page: number) => void;
}) {
  if (data.pages <= 1) return null;

  const pages = new Set([1, data.pages]);
  for (
    let page = Math.max(1, data.page - 2);
    page <= Math.min(data.pages, data.page + 2);
    page += 1
  ) {
    pages.add(page);
  }
  const visiblePages = [...pages].sort((left, right) => left - right);

  return (
    <nav className="pagination" aria-label="Paginación">
      <button
        className="pagination-arrow"
        disabled={data.page === 1}
        onClick={() => onPageChange(Math.max(1, data.page - 10))}
        aria-label="Retroceder diez páginas"
      >
        &lt;&lt;
      </button>
      <button
        className="pagination-arrow"
        disabled={data.page === 1}
        onClick={() => onPageChange(data.page - 1)}
        aria-label="Página anterior"
      >
        &lt;
      </button>
      {visiblePages.map((page, index) => (
        <span key={page} className="pagination-page-group">
          {index > 0 && page - visiblePages[index - 1] > 1 ? (
            <span className="pagination-ellipsis">...</span>
          ) : null}
          <button
            className={page === data.page ? "pagination-page active" : "pagination-page"}
            onClick={() => onPageChange(page)}
            aria-current={page === data.page ? "page" : undefined}
          >
            {page}
          </button>
        </span>
      ))}
      <button
        className="pagination-arrow"
        disabled={data.page >= data.pages}
        onClick={() => onPageChange(data.page + 1)}
        aria-label="Página siguiente"
      >
        &gt;
      </button>
      <button
        className="pagination-arrow"
        disabled={data.page >= data.pages}
        onClick={() => onPageChange(Math.min(data.pages, data.page + 10))}
        aria-label="Avanzar diez páginas"
      >
        &gt;&gt;
      </button>
    </nav>
  );
}
