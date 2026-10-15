import { useEffect, useRef, useState } from "react";

type SearchOption = { value: string; label: string };

export function SearchSelect({
  options,
  value,
  onChange,
  placeholder,
  required = false,
  actionLabel,
  onAction,
}: {
  options: SearchOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  required?: boolean;
  actionLabel?: string;
  onAction?: () => void;
}) {
  const selectedLabel = options.find((option) => option.value === value)?.label || "";
  const containerRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(selectedLabel);

  useEffect(() => setQuery(selectedLabel), [selectedLabel]);
  useEffect(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutsideClick);
    return () => document.removeEventListener("mousedown", closeOnOutsideClick);
  }, []);

  const filtered = options.filter((option) =>
    option.label.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  );

  return (
    <div className="search-select" ref={containerRef}>
      <button
        type="button"
        className="search-select-trigger"
        aria-expanded={open}
        onClick={() => {
          setQuery("");
          setOpen((current) => !current);
        }}
      >
        <span className={selectedLabel ? "" : "search-select-placeholder"}>
          {selectedLabel || placeholder}
        </span>
        <span aria-hidden="true">v</span>
      </button>
      {open && (
        <div className="search-select-menu">
          <input
            autoFocus
            value={query}
            placeholder="Escribe para buscar..."
            onChange={(event) => setQuery(event.target.value)}
          />
          {actionLabel && onAction && (
            <button
              type="button"
              className="search-select-action"
              onClick={() => {
                setOpen(false);
                onAction();
              }}
            >
              {actionLabel}
            </button>
          )}
          <div className="search-select-options">
            {filtered.map((option) => (
              <button
                type="button"
                key={option.value}
                className={option.value === value ? "selected" : ""}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
              >
                {option.label}
              </button>
            ))}
            {!filtered.length && <p>No se encontraron opciones.</p>}
          </div>
        </div>
      )}
      {required && (
        <input className="search-select-required" value={value} onChange={() => {}} required />
      )}
    </div>
  );
}
