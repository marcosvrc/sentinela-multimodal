import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ToastProvider, useToast } from "@/components/feedback/ToastProvider";

/**
 * Cobertura do sistema de notificacao global (toast) usado por toda tela
 * com fluxo de salvar/editar/excluir - ver
 * `frontend/src/components/feedback/ToastProvider.tsx`.
 */
function ToastTrigger() {
  const { showSuccess, showError } = useToast();
  return (
    <div>
      <button type="button" onClick={() => showSuccess("Paciente criado com sucesso.")}>
        Disparar sucesso
      </button>
      <button type="button" onClick={() => showError("Não foi possível salvar o paciente.")}>
        Disparar erro
      </button>
    </div>
  );
}

describe("ToastProvider", () => {
  it("exibe uma notificacao de sucesso com role status", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Disparar sucesso" }));

    const toast = screen.getByRole("status");
    expect(toast).toHaveTextContent("Paciente criado com sucesso.");
  });

  it("exibe uma notificacao de erro com role alert", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Disparar erro" }));

    const toast = screen.getByRole("alert");
    expect(toast).toHaveTextContent("Não foi possível salvar o paciente.");
  });

  it("empilha varias notificacoes disparadas em sequencia", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Disparar sucesso" }));
    fireEvent.click(screen.getByRole("button", { name: "Disparar erro" }));

    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("remove a notificacao ao clicar no botao de fechar", async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Disparar sucesso" }));
    expect(screen.getByRole("status")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Fechar notificação" }));

    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
  });

  it("remove a notificacao automaticamente apos o tempo limite", () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <ToastTrigger />
        </ToastProvider>,
      );

      fireEvent.click(screen.getByRole("button", { name: "Disparar sucesso" }));
      expect(screen.getByRole("status")).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(6000);
      });

      expect(screen.queryByRole("status")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it("lanca erro quando useToast e usado fora do ToastProvider", () => {
    function Broken() {
      useToast();
      return null;
    }
    expect(() => render(<Broken />)).toThrow(
      "useToast precisa ser usado dentro de um ToastProvider.",
    );
  });
});
