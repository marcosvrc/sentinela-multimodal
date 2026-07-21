import { useState } from "react";
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Modal } from "@/components/ui/Modal";

/**
 * Regressao: o dialogo nao pode roubar o foco do campo de texto a cada
 * digitacao. Isso aconteceu porque o efeito de foco/teclado do Modal
 * dependia de `onClose` - uma arrow function recriada a cada render do
 * formulario pai (inclusive a cada tecla digitada), o que reexecutava o
 * efeito e chamava `dialogRef.current?.focus()` a cada caractere.
 */
function ControlledModalWithTextField() {
  const [open, setOpen] = useState(true);
  const [value, setValue] = useState("");

  return (
    <Modal open={open} title="Formulario de teste" onClose={() => setOpen(false)}>
      <label htmlFor="test-input">Nome</label>
      <input id="test-input" value={value} onChange={(event) => setValue(event.target.value)} />
    </Modal>
  );
}

describe("Modal", () => {
  it("mantem o foco no campo de texto enquanto o usuario digita", () => {
    render(<ControlledModalWithTextField />);

    const input = screen.getByLabelText("Nome") as HTMLInputElement;
    input.focus();

    for (const char of "Ana") {
      fireEvent.change(input, { target: { value: input.value + char } });
    }

    expect(input).toHaveValue("Ana");
    expect(input).toHaveFocus();
  });

  it("fecha ao pressionar Escape", () => {
    let closed = false;
    render(
      <Modal open title="Dialogo" onClose={() => (closed = true)}>
        <p>Conteudo</p>
      </Modal>,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(closed).toBe(true);
  });
});
