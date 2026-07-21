import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "../src/App";

describe("App", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        if (url.toString().includes("/health")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                status: "ok",
                service: "SentinelHealth API",
                version: "0.1.0",
                environment: "test",
              }),
          });
        }
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      }) as unknown as typeof fetch,
    );
  });

  it("redireciona a raiz para /patients e mostra o titulo da pagina", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: /pacientes/i })).toBeInTheDocument();
  });

  it("pede para configurar o usuario de desenvolvimento quando nenhum esta selecionado", async () => {
    render(
      <MemoryRouter initialEntries={["/patients"]}>
        <App />
      </MemoryRouter>,
    );
    expect(
      await screen.findByText(/configure o usuario de desenvolvimento/i),
    ).toBeInTheDocument();
  });

  it("mostra o indicador de status da API depois da checagem de health", async () => {
    render(
      <MemoryRouter initialEntries={["/patients"]}>
        <App />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/api conectada/i)).toBeInTheDocument());
  });
});
