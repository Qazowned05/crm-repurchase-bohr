import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";

export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const [validationError, setValidationError] = useState("");
  const dialogRef = useRef<HTMLElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  const titleId = useId();

  onCloseRef.current = onClose;

  useEffect(() => {
    openerRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    dialog
      ?.querySelector<HTMLElement>(
        "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href]",
      )
      ?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialog) return;
      const items = [
        ...dialog.querySelectorAll<HTMLElement>(
          "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href]",
        ),
      ];
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      openerRef.current?.focus();
    };
  }, []);
  return createPortal(
    <div
      className="overlay"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <section
        ref={dialogRef}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onInvalid={(event) => {
          const field = event.target as HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
          setValidationError(field.validationMessage || "Revisa los campos obligatorios.");
        }}
        onInput={() => setValidationError("")}
      >
        <header>
          <h2 id={titleId}>{title}</h2>
          <button className="icon" type="button" onClick={onClose} aria-label="Cerrar diálogo">
            x
          </button>
        </header>
        {validationError && (
          <p className="form-error" role="alert">
            {validationError}
          </p>
        )}
        {children}
      </section>
    </div>,
    document.body,
  );
}
export function ConfirmModal({
  title = "Confirmar eliminación",
  message,
  onClose,
  onConfirm,
}: {
  title?: string;
  message: string;
  onClose: () => void;
  onConfirm: () => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await onConfirm();
      onClose();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No fue posible completar la acción.");
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit}>
        <p>{message}</p>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <footer>
          <button type="button" className="secondary" onClick={onClose} disabled={submitting}>
            Cancelar
          </button>
          <button className="danger" disabled={submitting}>
            {submitting ? "Eliminando..." : "Eliminar"}
          </button>
        </footer>
      </form>
    </Modal>
  );
}
