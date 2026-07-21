/**
 * Chamadas tipadas da API de administracao.
 * Ver backend/app/api/routes/administration.py.
 */
import { apiFetch } from "./client";
import type { PageResponse } from "@/types/api";
import type {
  AdminUser,
  AdminUserUpdateInput,
  AvailableRoles,
  CareUnit,
  CareUnitCreateInput,
  CareUnitUpdateInput,
  ClinicalRuleActionUpdateInput,
  ClinicalRuleSetDetail,
  ClinicalRuleSetSummary,
  ClinicalRuleUpdateInput,
  Employee,
  EmployeeCreateInput,
  EmployeeProfessionalType,
  EmployeeUpdateInput,
  MedicalSpecialty,
  MedicalSpecialtyCreateInput,
  MedicalSpecialtyUpdateInput,
  PublishRuleSetInput,
  RevokeSessionsInput,
  RollbackRuleSetInput,
} from "@/types/administration";
import type { FeatureFlags, FeatureFlagsUpdateInput } from "@/types/featureFlags";

export function listSpecialties(
  devSubject: string,
  params: { page?: number; pageSize?: number; search?: string; active?: boolean } = {},
): Promise<PageResponse<MedicalSpecialty>> {
  return apiFetch<PageResponse<MedicalSpecialty>>("/admin/specialties", {
    devSubject,
    searchParams: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 50,
      search: params.search || undefined,
      active: params.active,
    },
  });
}

export function createSpecialty(
  devSubject: string,
  data: MedicalSpecialtyCreateInput,
): Promise<MedicalSpecialty> {
  return apiFetch<MedicalSpecialty>("/admin/specialties", {
    devSubject,
    method: "POST",
    body: data,
  });
}

export function updateSpecialty(
  devSubject: string,
  specialtyId: string,
  data: MedicalSpecialtyUpdateInput,
): Promise<MedicalSpecialty> {
  return apiFetch<MedicalSpecialty>(`/admin/specialties/${specialtyId}`, {
    devSubject,
    method: "PATCH",
    body: data,
  });
}

export function listEmployees(
  devSubject: string,
  params: {
    page?: number;
    pageSize?: number;
    search?: string;
    active?: boolean;
    professionalType?: EmployeeProfessionalType;
  } = {},
): Promise<PageResponse<Employee>> {
  return apiFetch<PageResponse<Employee>>("/admin/employees", {
    devSubject,
    searchParams: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      search: params.search || undefined,
      active: params.active,
      professional_type: params.professionalType,
    },
  });
}

export function getAvailableRoles(
  devSubject: string,
  professionalType: EmployeeProfessionalType,
): Promise<AvailableRoles> {
  return apiFetch<AvailableRoles>("/admin/employees/available-roles", {
    devSubject,
    searchParams: { professional_type: professionalType },
  });
}

export function createEmployee(devSubject: string, data: EmployeeCreateInput): Promise<Employee> {
  return apiFetch<Employee>("/admin/employees", { devSubject, method: "POST", body: data });
}

export function updateEmployee(
  devSubject: string,
  employeeId: string,
  data: EmployeeUpdateInput,
): Promise<Employee> {
  return apiFetch<Employee>(`/admin/employees/${employeeId}`, {
    devSubject,
    method: "PATCH",
    body: data,
  });
}

export function listClinicalRuleSets(
  devSubject: string,
  params: { page?: number; pageSize?: number; code?: string; status?: string } = {},
): Promise<PageResponse<ClinicalRuleSetSummary>> {
  return apiFetch<PageResponse<ClinicalRuleSetSummary>>("/admin/clinical-rule-sets", {
    devSubject,
    searchParams: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 50,
      code: params.code,
      status: params.status,
    },
  });
}

export function getClinicalRuleSet(
  devSubject: string,
  ruleSetId: string,
): Promise<ClinicalRuleSetDetail> {
  return apiFetch<ClinicalRuleSetDetail>(`/admin/clinical-rule-sets/${ruleSetId}`, { devSubject });
}

export function publishClinicalRuleSet(
  devSubject: string,
  ruleSetId: string,
  data: PublishRuleSetInput,
): Promise<ClinicalRuleSetDetail> {
  return apiFetch<ClinicalRuleSetDetail>(`/admin/clinical-rule-sets/${ruleSetId}/publish`, {
    devSubject,
    method: "POST",
    body: data,
  });
}

export function rollbackClinicalRuleSet(
  devSubject: string,
  ruleSetId: string,
  data: RollbackRuleSetInput,
): Promise<ClinicalRuleSetDetail> {
  return apiFetch<ClinicalRuleSetDetail>(`/admin/clinical-rule-sets/${ruleSetId}/rollback`, {
    devSubject,
    method: "POST",
    body: data,
  });
}

export function updateClinicalRule(
  devSubject: string,
  ruleSetId: string,
  ruleId: string,
  data: ClinicalRuleUpdateInput,
): Promise<ClinicalRuleSetDetail> {
  return apiFetch<ClinicalRuleSetDetail>(
    `/admin/clinical-rule-sets/${ruleSetId}/rules/${ruleId}`,
    { devSubject, method: "PATCH", body: data },
  );
}

export function updateClinicalRuleAction(
  devSubject: string,
  ruleSetId: string,
  actionId: string,
  data: ClinicalRuleActionUpdateInput,
): Promise<ClinicalRuleSetDetail> {
  return apiFetch<ClinicalRuleSetDetail>(
    `/admin/clinical-rule-sets/${ruleSetId}/actions/${actionId}`,
    { devSubject, method: "PATCH", body: data },
  );
}

// --- Usuarios/papeis de acesso ----------------------------------------------

export function listUsers(
  devSubject: string,
  params: {
    page?: number;
    pageSize?: number;
    search?: string;
    role?: string;
    active?: boolean;
  } = {},
): Promise<PageResponse<AdminUser>> {
  return apiFetch<PageResponse<AdminUser>>("/admin/users", {
    devSubject,
    searchParams: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 20,
      search: params.search || undefined,
      role: params.role || undefined,
      active: params.active,
    },
  });
}

// Sem createUser: a conta de acesso e criada junto com o funcionario
// (ver createEmployee acima) - esta tela e apenas consulta/gestao.

export function updateUser(
  devSubject: string,
  userId: string,
  data: AdminUserUpdateInput,
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${userId}`, { devSubject, method: "PATCH", body: data });
}

export function revokeUserSessions(
  devSubject: string,
  userId: string,
  data: RevokeSessionsInput,
): Promise<void> {
  return apiFetch<void>(`/admin/users/${userId}/revoke-sessions`, {
    devSubject,
    method: "POST",
    body: data,
  });
}

// --- Unidades assistenciais --------------------------------------------------

export function listCareUnits(
  devSubject: string,
  params: { page?: number; pageSize?: number; search?: string; active?: boolean } = {},
): Promise<PageResponse<CareUnit>> {
  return apiFetch<PageResponse<CareUnit>>("/admin/care-units", {
    devSubject,
    searchParams: {
      page: params.page ?? 1,
      page_size: params.pageSize ?? 50,
      search: params.search || undefined,
      active: params.active,
    },
  });
}

export function createCareUnit(devSubject: string, data: CareUnitCreateInput): Promise<CareUnit> {
  return apiFetch<CareUnit>("/admin/care-units", { devSubject, method: "POST", body: data });
}

export function updateCareUnit(
  devSubject: string,
  careUnitId: string,
  data: CareUnitUpdateInput,
): Promise<CareUnit> {
  return apiFetch<CareUnit>(`/admin/care-units/${careUnitId}`, {
    devSubject,
    method: "PATCH",
    body: data,
  });
}

// --- Feature flags (IA/multimodalidade) -------------------------------------

export function getFeatureFlags(devSubject: string): Promise<FeatureFlags> {
  return apiFetch<FeatureFlags>("/admin/feature-flags", { devSubject });
}

export function updateFeatureFlags(
  devSubject: string,
  data: FeatureFlagsUpdateInput,
): Promise<FeatureFlags> {
  return apiFetch<FeatureFlags>("/admin/feature-flags", {
    devSubject,
    method: "PATCH",
    body: data,
  });
}
