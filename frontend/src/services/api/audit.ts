/** Ver backend/app/api/routes/audit.py. */
import { apiFetch } from "./client";
import type { PageResponse } from "@/types/api";
import type { AuditEvent } from "@/types/audit";

export interface AuditEventFilters {
  actor?: string;
  action?: string;
  resourceType?: string;
  resourceId?: string;
  result?: string;
  page?: number;
  pageSize?: number;
}

export function listAuditEvents(
  devSubject: string,
  filters: AuditEventFilters = {},
): Promise<PageResponse<AuditEvent>> {
  return apiFetch<PageResponse<AuditEvent>>("/audit/events", {
    devSubject,
    searchParams: {
      actor: filters.actor || undefined,
      action: filters.action || undefined,
      resource_type: filters.resourceType || undefined,
      resource_id: filters.resourceId || undefined,
      result: filters.result || undefined,
      page: filters.page ?? 1,
      page_size: filters.pageSize ?? 20,
    },
  });
}
