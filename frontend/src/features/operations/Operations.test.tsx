import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Operations } from "./Operations";

function response(body: unknown, ok = true) {
  return {
    ok,
    status: ok ? 200 : 400,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response;
}

describe("Operations", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the shared API path for preview and submits import choices", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ items: [], pages: 0 }))
      .mockResolvedValueOnce(response({ items: [], pages: 0 }))
      .mockResolvedValueOnce(
        response({
          id: "import-1",
          state: "PREVIEW_READY",
          total_rows: 1,
          valid_rows: 1,
          rejected_rows: 0,
          errors: [],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<Operations />);
    const file = new File(["sheet"], "clientes.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    fireEvent.change(screen.getByLabelText("Archivo Excel"), { target: { files: [file] } });
    fireEvent.click(screen.getByLabelText("Permitir actualizar clientes o productos existentes"));
    fireEvent.click(screen.getByRole("button", { name: "Validar archivo" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
    expect(fetchMock.mock.calls[2][0]).toBe("/api/v1/imports/customers/preview");
    const body = fetchMock.mock.calls[2][1]?.body as FormData;
    expect(body.get("allow_updates")).toBe("true");
    expect(await screen.findByText(/1 válidas de 1 filas/)).toBeInTheDocument();
  });

  it("shows a download failure instead of leaving the action silent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(response({ detail: "Plantilla no disponible" }, false)),
    );
    render(<Operations />);
    fireEvent.click(screen.getByRole("button", { name: "Descargar plantilla" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Plantilla no disponible");
  });
});
