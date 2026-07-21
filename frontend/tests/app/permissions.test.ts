import { describe, expect, it } from "vitest";
import { hasPermission, permissionForPath } from "@/app/permissions";
import { UserRole } from "@/types/enums.generated";

describe("permissions", () => {
  it("permite pacientes/analises apenas para medico e enfermeiro", () => {
    expect(hasPermission(UserRole.MEDICO, "patients")).toBe(true);
    expect(hasPermission(UserRole.ENFERMEIRO, "patients")).toBe(true);
    expect(hasPermission(UserRole.AUDITOR, "patients")).toBe(false);
    expect(hasPermission(UserRole.ADMINISTRADOR_TECNICO, "patients")).toBe(false);
  });

  it("permite auditoria para auditor e administradores, nao para clinicos", () => {
    expect(hasPermission(UserRole.AUDITOR, "audit")).toBe(true);
    expect(hasPermission(UserRole.ADMINISTRADOR_TECNICO, "audit")).toBe(true);
    expect(hasPermission(UserRole.ADMINISTRADOR_CLINICO, "audit")).toBe(true);
    expect(hasPermission(UserRole.MEDICO, "audit")).toBe(false);
  });

  it("permite administracao apenas para os dois papeis de administrador", () => {
    expect(hasPermission(UserRole.ADMINISTRADOR_TECNICO, "admin")).toBe(true);
    expect(hasPermission(UserRole.ADMINISTRADOR_CLINICO, "admin")).toBe(true);
    expect(hasPermission(UserRole.MEDICO, "admin")).toBe(false);
    expect(hasPermission(UserRole.AUDITOR, "admin")).toBe(false);
  });

  it("nega tudo quando nao ha papel resolvido", () => {
    expect(hasPermission(undefined, "patients")).toBe(false);
    expect(hasPermission("", "admin")).toBe(false);
  });

  it("resolve a permissao pelo prefixo de rota mais especifico", () => {
    expect(permissionForPath("/patients")).toBe("patients");
    expect(permissionForPath("/patients/123")).toBe("patients");
    expect(permissionForPath("/analyses/new")).toBe("analyses");
    expect(permissionForPath("/admin/users")).toBe("admin");
    expect(permissionForPath("/audit")).toBe("audit");
    expect(permissionForPath("/not-found")).toBeNull();
  });
});
