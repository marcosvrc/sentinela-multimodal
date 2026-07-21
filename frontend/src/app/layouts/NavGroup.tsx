import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { ChevronDown, type LucideIcon } from "lucide-react";
import styles from "./AppShell.module.css";

export interface NavChildItem {
  to: string;
  label: string;
}

interface NavGroupProps {
  label: string;
  icon?: LucideIcon;
  children: NavChildItem[];
}

/**
 * Item de navegacao com submenu expansivel. O item pai nunca navega por
 * si só; ele apenas expande/recolhe os filhos. Abre automaticamente
 * quando a rota ativa pertence a um dos filhos.
 */
export function NavGroup({ label, icon: Icon, children }: NavGroupProps) {
  const location = useLocation();
  const hasActiveChild = children.some((child) => location.pathname.startsWith(child.to));
  const [open, setOpen] = useState(hasActiveChild);

  const groupId = `nav-group-${label.toLowerCase().replace(/\s+/g, "-")}`;

  return (
    <li className={styles.navGroup}>
      <button
        type="button"
        className={[styles.navGroupToggle, hasActiveChild && styles.navGroupToggleActive]
          .filter(Boolean)
          .join(" ")}
        aria-expanded={open}
        aria-controls={groupId}
        onClick={() => setOpen((current) => !current)}
      >
        <span className={styles.navGroupLabel}>
          {Icon && <Icon className={styles.navIcon} aria-hidden="true" size={18} strokeWidth={1.75} />}
          <span>{label}</span>
        </span>
        <ChevronDown
          aria-hidden="true"
          size={16}
          strokeWidth={2}
          className={[styles.chevron, open && styles.chevronOpen].filter(Boolean).join(" ")}
        />
      </button>
      {open && (
        <ul id={groupId} className={styles.subNavList}>
          {children.map((child) => (
            <li key={child.to}>
              <NavLink
                to={child.to}
                className={({ isActive }) =>
                  [styles.subNavLink, isActive && styles.navLinkActive].filter(Boolean).join(" ")
                }
              >
                {child.label}
              </NavLink>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
