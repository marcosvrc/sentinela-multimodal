/**
 * Tipos do modulo de administracao.
 * Espelha backend/app/api/schemas/administration.py.
 */

export interface MedicalSpecialty {
  id: string;
  name: string;
  active: boolean;
  created_at: string;
}

export interface MedicalSpecialtyCreateInput {
  name: string;
}

export interface MedicalSpecialtyUpdateInput {
  name?: string;
  active?: boolean;
}

/** Profissao-base do funcionario - determina os papeis de acesso permitidos. */
export type EmployeeProfessionalType = "MEDICO" | "ENFERMEIRO";

export interface Employee {
  id: string;
  full_name: string;
  cpf: string;
  registration_number: string;
  email: string;
  specialty_id: string | null;
  professional_type: EmployeeProfessionalType;
  active: boolean;
  created_at: string;
  updated_at: string;
  /** Dados da conta de acesso vinculada (criada junto com o funcionario). */
  user_id: string | null;
  external_subject: string | null;
  role: string | null;
}

export interface EmployeeCreateInput {
  full_name: string;
  cpf: string;
  registration_number: string;
  email: string;
  specialty_id?: string;
  professional_type: EmployeeProfessionalType;
  role: string;
  external_subject: string;
}

export interface EmployeeUpdateInput {
  full_name?: string;
  email?: string;
  specialty_id?: string;
  active?: boolean;
  role?: string;
}

export interface AvailableRoles {
  professional_type: EmployeeProfessionalType;
  roles: string[];
}

export interface ClinicalRuleApproval {
  id: string;
  approver: string;
  decision: string;
  justification: string;
  decided_at: string;
}

export interface ClinicalRuleSetSummary {
  id: string;
  code: string;
  version: string;
  population: string;
  status: string;
  effective_from: string;
  effective_to: string | null;
  created_at: string;
}

export interface ClinicalRule {
  id: string;
  rule_key: string;
  when: string;
  risk_level: number;
  classification_label: string;
  notes: string | null;
  position: number;
}

export interface ClinicalRuleUpdateInput {
  when: string;
  risk_level: number;
  classification_label: string;
  notes?: string | null;
}

export interface ClinicalRuleAction {
  id: string;
  risk_level: number;
  description: string;
}

export interface ClinicalRuleActionUpdateInput {
  description: string;
}

export interface ClinicalRuleSetDetail extends ClinicalRuleSetSummary {
  required_inputs: string[];
  exclusions: string[];
  content_hash: string;
  approvals: ClinicalRuleApproval[];
  rules: ClinicalRule[];
  actions: ClinicalRuleAction[];
}

/** `approver_employee_id` referencia um `Employee` medico e ativo
 * cadastrado (selecionado em uma lista, nunca digitado livremente - ver
 * `app.administration.service.get_active_doctor_for_approval`). */
export interface PublishRuleSetInput {
  approver_employee_id: string;
  justification: string;
}

export interface RollbackRuleSetInput {
  approver_employee_id: string;
  justification: string;
}

/**
 * Usuarios/papeis de acesso. Espelho local de instituicao/papel - o
 * provisionamento de credencial (senha/MFA) em si acontece no Cognito,
 * fora deste modulo (ver backend/app/administration/service.py, docstring
 * da secao "Usuarios").
 */
export interface AdminUser {
  id: string;
  external_subject: string;
  full_name: string;
  role: string;
  active: boolean;
  created_at: string;
}

export interface AdminUserUpdateInput {
  role?: string;
  active?: boolean;
}

export interface RevokeSessionsInput {
  reason: string;
}

/** Unidade assistencial (eixo "unidade + vinculo" do controle de acesso). */
export interface CareUnit {
  id: string;
  name: string;
  active: boolean;
}

export interface CareUnitCreateInput {
  name: string;
}

export interface CareUnitUpdateInput {
  name?: string;
  active?: boolean;
}
