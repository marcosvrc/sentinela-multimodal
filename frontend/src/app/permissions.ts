/**
 * Mapeamento de papel -> rotas/itens de navegacao autorizados.
 *
 * Espelha as dependencias `require_role` do backend (a fonte real de
 * autorizacao - ver cada arquivo referenciado abaixo). Este mapa e usado
 * apenas para decidir o que MOSTRAR na navegacao - a ocultacao de menus e
 * apenas conveniencia visual, o backend continua responsavel pela
 * autorizacao efetiva. Se este mapa ficar desatualizado em relacao ao
 * backend, o pior cenario e um item de menu aparecer/desaparecer errado -
 * nunca uma falha de seguranca, porque toda rota HTTP real segue
 * validando o papel de novo.
 *
 * Fontes por chave:
 * - "patients":       backend/app/api/routes/patients.py (_require_clinical_staff)
 * - "analyses":       backend/app/api/routes/media.py + orchestrator.py + reports.py (_require_clinical_staff)
 * - "audit":          backend/app/api/routes/audit.py (_require_audit_access)
 * - "admin":          backend/app/api/routes/administration.py (_require_admin - especialidades/funcionarios/regras/usuarios/unidades)
 */
import { UserRole } from "@/types/enums.generated";

export type NavPermissionKey = "patients" | "analyses" | "audit" | "admin";

const ROLES_BY_PERMISSION: Record<NavPermissionKey, UserRole[]> = {
  patients: [UserRole.MEDICO, UserRole.ENFERMEIRO],
  analyses: [UserRole.MEDICO, UserRole.ENFERMEIRO],
  audit: [UserRole.AUDITOR, UserRole.ADMINISTRADOR_TECNICO, UserRole.ADMINISTRADOR_CLINICO],
  admin: [UserRole.ADMINISTRADOR_TECNICO, UserRole.ADMINISTRADOR_CLINICO],
};

/** Rota (prefixo) -> permissao exigida. Usada pelo guard de rotas (RequireRole). */
export const ROUTE_PERMISSIONS: { prefix: string; permission: NavPermissionKey }[] = [
  { prefix: "/patients", permission: "patients" },
  { prefix: "/analyses", permission: "analyses" },
  { prefix: "/audit", permission: "audit" },
  { prefix: "/admin", permission: "admin" },
];

export function hasPermission(role: string | undefined, permission: NavPermissionKey): boolean {
  if (!role) return false;
  return (ROLES_BY_PERMISSION[permission] as string[]).includes(role);
}

/** Permissao exigida pela rota mais especifica que casar com o path, se houver. */
export function permissionForPath(pathname: string): NavPermissionKey | null {
  const match = ROUTE_PERMISSIONS.filter((route) => pathname.startsWith(route.prefix)).sort(
    (a, b) => b.prefix.length - a.prefix.length,
  )[0];
  return match?.permission ?? null;
}
