/**
 * Identidade autenticada atual (`GET /me`). Ver backend/app/api/routes/me.py.
 */
import { apiFetch } from "./client";
import type { CurrentUser } from "@/types/me";

export function getCurrentUser(devSubject: string): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/me", { devSubject });
}
