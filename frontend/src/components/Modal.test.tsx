import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmModal, Modal } from "./Modal";

describe("Modal", () => {
  it("closes with Escape and restores focus to the opener", () => {
    const onClose = vi.fn();
    const opener = document.createElement("button");
    document.body.appendChild(opener);
    opener.focus();
    const { unmount } = render(
      <Modal title="Editar" onClose={onClose}>
        <input aria-label="Nombre" />
      </Modal>,
    );
    expect(screen.getByRole("dialog")).toHaveAttribute("aria-modal", "true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    unmount();
    expect(opener).toHaveFocus();
    opener.remove();
  });

  it("keeps confirmation errors visible", async () => {
    render(
      <ConfirmModal
        message="Eliminar registro"
        onClose={vi.fn()}
        onConfirm={() => Promise.reject(new Error("No autorizado"))}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Eliminar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("No autorizado");
  });

  it("keeps input focus when typing changes the close callback", async () => {
    const user = userEvent.setup();

    function StatefulModal() {
      const [value, setValue] = useState("");
      const [closedWith, setClosedWith] = useState("");

      return (
        <>
          <Modal title="Editar" onClose={() => setClosedWith(value)}>
            <input
              aria-label="Nombre"
              value={value}
              onChange={(event) => setValue(event.target.value)}
            />
          </Modal>
          <output>{closedWith}</output>
        </>
      );
    }

    render(<StatefulModal />);
    const input = screen.getByRole("textbox", { name: "Nombre" });
    await user.click(input);
    await user.type(input, "Ana");

    expect(input).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByText("Ana")).toBeInTheDocument();
  });
});
