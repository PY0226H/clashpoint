import { http, toApiError } from "@echoisle/api-client";

export type OpsRole = "ops_admin" | "ops_reviewer" | "ops_viewer";

export type OpsPermissionFlags = {
  debateManage: boolean;
  judgeReview: boolean;
  judgeRejudge: boolean;
  roleManage: boolean;
};

export type GetOpsRbacMeOutput = {
  userId: number;
  isOwner: boolean;
  role?: string | null;
  permissions: OpsPermissionFlags;
};

export type OpsRoleAssignment = {
  userId: number;
  userEmail: string;
  userFullname: string;
  role: OpsRole;
  grantedBy: number;
  createdAt: string;
  updatedAt: string;
};

export type ListOpsRoleAssignmentsOutput = {
  items: OpsRoleAssignment[];
};

export type RevokeOpsRoleOutput = {
  userId: number;
  removed: boolean;
};

export function toOpsDomainError(error: unknown): string {
  return toApiError(error);
}

export async function getOpsRbacMe(): Promise<GetOpsRbacMeOutput> {
  const response = await http.get<GetOpsRbacMeOutput>("/debate/ops/rbac/me");
  return response.data;
}

export async function listOpsRoleAssignments(): Promise<ListOpsRoleAssignmentsOutput> {
  const response = await http.get<ListOpsRoleAssignmentsOutput>("/debate/ops/rbac/roles");
  return response.data;
}

export async function upsertOpsRoleAssignment(
  userId: number,
  role: OpsRole
): Promise<OpsRoleAssignment> {
  const normalizedUserId = Math.floor(Number(userId) || 0);
  const normalizedRole = String(role || "").trim().toLowerCase() as OpsRole;
  const response = await http.put<OpsRoleAssignment>(`/debate/ops/rbac/roles/${normalizedUserId}`, {
    role: normalizedRole
  });
  return response.data;
}

export async function revokeOpsRoleAssignment(userId: number): Promise<RevokeOpsRoleOutput> {
  const normalizedUserId = Math.floor(Number(userId) || 0);
  const response = await http.delete<RevokeOpsRoleOutput>(`/debate/ops/rbac/roles/${normalizedUserId}`);
  return response.data;
}
