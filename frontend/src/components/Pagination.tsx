import { useState } from "react";
import type { Paged } from "../services/types";

export const PAGE_SIZE = 10;

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
  onPageChange: (page: number) => void | Promise<void>;
}) {
  const [loading, setLoading] = useState(false);
  if (data.pages <= 1) return null;

  const changePage = async (page: number) => {
    if (loading || page === data.page) return;
    setLoading(true);
    try {
      await onPageChange(page);
    } finally {
      setLoading(false);
    }
  };

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
    <nav
      className={`pagination${loading ? " is-loading" : ""}`}
      aria-label="Paginación"
      aria-busy={loading}
    >
      <button
        className="pagination-arrow"
        disabled={loading || data.page === 1}
        onClick={() => changePage(Math.max(1, data.page - 10))}
        aria-label="Retroceder diez páginas"
      >
        &lt;&lt;
      </button>
      <button
        className="pagination-arrow"
        disabled={loading || data.page === 1}
        onClick={() => changePage(data.page - 1)}
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
            disabled={loading}
            onClick={() => changePage(page)}
            aria-current={page === data.page ? "page" : undefined}
          >
            {page}
          </button>
        </span>
      ))}
      <button
        className="pagination-arrow"
        disabled={loading || data.page >= data.pages}
        onClick={() => changePage(data.page + 1)}
        aria-label="Página siguiente"
      >
        &gt;
      </button>
      <button
        className="pagination-arrow"
        disabled={loading || data.page >= data.pages}
        onClick={() => changePage(Math.min(data.pages, data.page + 10))}
        aria-label="Avanzar diez páginas"
      >
        &gt;&gt;
      </button>
      {loading && (
        <span className="pagination-loading" role="status">
          Cargando
        </span>
      )}
    </nav>
  );
}
