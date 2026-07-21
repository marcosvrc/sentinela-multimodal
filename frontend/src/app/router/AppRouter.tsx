import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/app/layouts/AppShell";
import { RequireRole } from "@/app/router/RequireRole";
import { PatientsListPage } from "@/features/patients/PatientsListPage";
import { PatientCreatePage } from "@/features/patients/PatientCreatePage";
import { PatientEditPage } from "@/features/patients/PatientEditPage";
import { PatientDetailPage } from "@/features/patients/PatientDetailPage";
import { AnalysisNewPage } from "@/features/analyses/AnalysisNewPage";
import { AnalysesListPage } from "@/features/analyses/AnalysesListPage";
import { AnalysisDetailPage } from "@/features/analyses/AnalysisDetailPage";
import { AnalysisReviewPage } from "@/features/analyses/AnalysisReviewPage";
import { AuditPage } from "@/features/audit/AuditPage";
import { SpecialtiesPage } from "@/features/admin/SpecialtiesPage";
import { EmployeesPage } from "@/features/admin/EmployeesPage";
import { ClinicalRuleSetsPage } from "@/features/admin/ClinicalRuleSetsPage";
import { UsersPage } from "@/features/admin/UsersPage";
import { CareUnitsPage } from "@/features/admin/CareUnitsPage";
import { FeatureFlagsPage } from "@/features/admin/FeatureFlagsPage";
import { AccessDeniedPage } from "@/features/misc/AccessDeniedPage";
import { NotFoundPage } from "@/features/misc/NotFoundPage";

/**
 * Rotas implementadas ate aqui.
 * Login e "Visao geral" (`/dashboard`) entram em iteracoes futuras, pois
 * dependem de Identidade real.
 *
 * Cada grupo de rotas e envolvido por `RequireRole` com a mesma permissao
 * declarada em `app/permissions.ts` para os itens de menu correspondentes -
 * conveniencia de navegacao (redireciona para `/access-denied`), nao a
 * autorizacao real (o backend segue validando cada chamada).
 */
export function AppRouter() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<Navigate to="/patients" replace />} />
        <Route
          path="/patients"
          element={
            <RequireRole permission="patients">
              <PatientsListPage />
            </RequireRole>
          }
        />
        <Route
          path="/patients/new"
          element={
            <RequireRole permission="patients">
              <PatientCreatePage />
            </RequireRole>
          }
        />
        <Route
          path="/patients/:patientId"
          element={
            <RequireRole permission="patients">
              <PatientDetailPage />
            </RequireRole>
          }
        />
        <Route
          path="/patients/:patientId/edit"
          element={
            <RequireRole permission="patients">
              <PatientEditPage />
            </RequireRole>
          }
        />
        <Route
          path="/patients/:patientId/analyses/new"
          element={
            <RequireRole permission="analyses">
              <AnalysisNewPage />
            </RequireRole>
          }
        />
        <Route
          path="/analyses/new"
          element={
            <RequireRole permission="analyses">
              <AnalysisNewPage />
            </RequireRole>
          }
        />
        <Route
          path="/analyses"
          element={
            <RequireRole permission="analyses">
              <AnalysesListPage />
            </RequireRole>
          }
        />
        <Route
          path="/analyses/:analysisId"
          element={
            <RequireRole permission="analyses">
              <AnalysisDetailPage />
            </RequireRole>
          }
        />
        <Route
          path="/analyses/:analysisId/review"
          element={
            <RequireRole permission="analyses">
              <AnalysisReviewPage />
            </RequireRole>
          }
        />
        <Route
          path="/audit"
          element={
            <RequireRole permission="audit">
              <AuditPage />
            </RequireRole>
          }
        />
        <Route path="/admin" element={<Navigate to="/admin/users" replace />} />
        <Route
          path="/admin/specialties"
          element={
            <RequireRole permission="admin">
              <SpecialtiesPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/employees"
          element={
            <RequireRole permission="admin">
              <EmployeesPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/clinical-rules"
          element={
            <RequireRole permission="admin">
              <ClinicalRuleSetsPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/users"
          element={
            <RequireRole permission="admin">
              <UsersPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/care-units"
          element={
            <RequireRole permission="admin">
              <CareUnitsPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/feature-flags"
          element={
            <RequireRole permission="admin">
              <FeatureFlagsPage />
            </RequireRole>
          }
        />
        <Route path="/access-denied" element={<AccessDeniedPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
