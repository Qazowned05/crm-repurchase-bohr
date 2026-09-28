import type { FormEvent, ReactNode } from "react";
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
  return createPortal(
    <div className="overlay" role="presentation" onMouseDown={onClose}>
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon" onClick={onClose}>
            x
          </button>
        </header>
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
  async function submit(e: FormEvent) {
    e.preventDefault();
    await onConfirm();
    onClose();
  }
  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit}>
        <p>{message}</p>
        <footer>
          <button type="button" className="secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="danger">Eliminar</button>
        </footer>
      </form>
    </Modal>
  );
}
