import { NavLink, Outlet } from "react-router-dom";
import {
  ClipboardList,
  PlusCircle,
  Settings,
  ShieldCheck,
  Users,
  type LucideIcon,
} from "lucide-react";
import styles from "./AppShell.module.css";
import { NavGroup } from "./NavGroup";
import { DevSessionBanner } from "@/features/dev/InstitutionBanner";
import { ApiStatusIndicator } from "@/components/layout/ApiStatusIndicator";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { hasPermission, type NavPermissionKey } from "@/app/permissions";
import { roleLabel } from "@/app/enumLabels";
import { Logo } from "@/components/ui/Logo";

interface NavItemDef {
  to: string;
  label: string;
  icon: LucideIcon;
  permission: NavPermissionKey;
}

// Cada item declara a permissao exigida pela rota real (ver
// app/permissions.ts) - a lista visivel na sidebar e filtrada pelo papel do
// usuario ativo (resolvido via `GET /me`, nunca inferido no cliente).
// "Visao geral" (`/dashboard`) fica para uma iteracao futura.
const NAV_ITEMS: NavItemDef[] = [
  { to: "/patients", label: "Pacientes", icon: Users, permission: "patients" },
  { to: "/analyses/new", label: "Nova analise", icon: PlusCircle, permission: "analyses" },
  { to: "/analyses", label: "Histórico", icon: ClipboardList, permission: "analyses" },
  { to: "/audit", label: "Auditoria", icon: ShieldCheck, permission: "audit" },
];

// "Administracao" e um item de menu com submenu - cada filho e uma
// rota/tela propria com seu proprio CRUD, nao mais abas dentro de uma
// unica tela (ver AdminLayout removido). Todos os filhos exigem a mesma
// permissao ("admin"), entao o grupo inteiro aparece/desaparece junto.
const ADMIN_SUBMENU = [
  { to: "/admin/users", label: "Usuarios e papeis" },
  { to: "/admin/specialties", label: "Especialidades" },
  { to: "/admin/employees", label: "Funcionarios" },
  { to: "/admin/clinical-rules", label: "Dados clinicos (regras)" },
  { to: "/admin/care-units", label: "Unidades assistenciais" },
  { to: "/admin/feature-flags", label: "Feature flags" },
];

function initialsFromName(name: string): string {
  const parts = name.split(" ").filter(Boolean);
  const initials = parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "");
  return initials.join("") || "?";
}

/**
 * Casca principal da aplicacao.
 * Sidebar fixa 240px no desktop, topbar 64-72px, conteudo max 1440px.
 * Sidebar clara com item ativo em destaque, topbar com avatar/saudacao
 * do usuario.
 *
 * A navegacao exibida depende do papel do usuario ativo: cada item
 * declara a permissao exigida pela rota real (app/permissions.ts) e so
 * aparece quando `hasPermission` confirma que o papel resolvido por
 * `GET /me` tem acesso. Isso e apenas conveniencia visual - o backend
 * continua sendo a autoridade de autorizacao em cada chamada.
 */
export function AppShell() {
  const { subject, user, role } = useCurrentUser();

  const visibleNavItems = NAV_ITEMS.filter((item) => hasPermission(role, item.permission));
  const showAdminSubmenu = hasPermission(role, "admin");

  return (
    <div className={styles.shell}>
      <a href="#main-content" className={styles.skipLink}>
        Pular para o conteudo principal
      </a>

      <aside className={styles.sidebar} aria-label="Navegação principal">
        <div className={styles.brand}>
          <Logo className={styles.brandIcon} />
          <span>SentinelHealth</span>
        </div>
        <p className={styles.navSectionLabel}>Menu principal</p>
        <nav>
          <ul className={styles.navList}>
            {visibleNavItems.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      [styles.navLink, isActive && styles.navLinkActive].filter(Boolean).join(" ")
                    }
                  >
                    <Icon className={styles.navIcon} aria-hidden="true" size={18} strokeWidth={1.75} />
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              );
            })}
            {showAdminSubmenu && (
              <NavGroup label="Administração" icon={Settings} children={ADMIN_SUBMENU} />
            )}
          </ul>
        </nav>

        <div className={styles.sidebarFooter}>
          <p className={styles.sidebarFooterTitle}>Precisa de ajuda?</p>
          <p className={styles.sidebarFooterText}>Consulte o manual de execucao do sistema.</p>
        </div>
      </aside>

      <div className={styles.content}>
        <header className={styles.topbar}>
          <span className={styles.topbarTitle}>Apoio a analise clinica multimodal</span>
          <div className={styles.topbarActions}>
            <ApiStatusIndicator />
            {subject && user && (
              <div className={styles.userChip}>
                <span className={styles.avatar} aria-hidden="true">
                  {initialsFromName(user.full_name)}
                </span>
                <span className={styles.userGreeting}>
                  Ola,
                  <span className={styles.userName}>
                    {user.full_name} · {roleLabel(user.role)}
                  </span>
                </span>
              </div>
            )}
          </div>
        </header>

        <DevSessionBanner />

        <main id="main-content" className={styles.main}>
          <div className={styles.mainInner}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
