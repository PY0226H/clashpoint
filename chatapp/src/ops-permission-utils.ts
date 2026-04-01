import type {
  OpsPermissionDenied,
  OpsPermissionInputKey,
  OpsPermissionKey,
  OpsRbacMe,
  OpsRbacPermissions,
} from './types/api';

const OPS_PERMISSION_HINTS: Record<string, string> = {
  debate_manage: '当前账号没有“场次管理”权限（需 ops_admin）',
  judge_review: '当前账号没有“判决审阅”权限（需 ops_viewer / ops_reviewer / ops_admin）',
  judge_rejudge: '当前账号没有“复核触发”权限（需 ops_reviewer / ops_admin）',
  role_manage: '仅 platform admin 可以管理 Ops 角色',
};

function normalizePermissionKey(permission: OpsPermissionInputKey | string | null | undefined): OpsPermissionKey | '' {
  const value = String(permission || '').trim();
  if (!value) {
    return '';
  }
  if (value === 'debate_manage' || value === 'debateManage') {
    return 'debateManage';
  }
  if (value === 'judge_review' || value === 'judgeReview') {
    return 'judgeReview';
  }
  if (value === 'judge_rejudge' || value === 'judgeRejudge') {
    return 'judgeRejudge';
  }
  if (value === 'role_manage' || value === 'roleManage') {
    return 'roleManage';
  }
  return '';
}

export function emptyOpsRbacMe(): OpsRbacMe {
  const permissions: OpsRbacPermissions = {
    debateManage: false,
    judgeReview: false,
    judgeRejudge: false,
    roleManage: false,
  };
  return {
    userId: 0,
    isOwner: false,
    role: null,
    permissions,
  };
}

export function normalizeOpsRbacMe(payload: Partial<OpsRbacMe> | Record<string, unknown> | null | undefined): OpsRbacMe {
  const value = payload || {};
  const valueRecord = value as Record<string, unknown>;
  const permissions = (valueRecord.permissions || {}) as Partial<OpsRbacPermissions>;
  return {
    userId: Number(valueRecord.userId || 0),
    isOwner: !!valueRecord.isOwner,
    role: valueRecord.role == null ? null : String(valueRecord.role),
    permissions: {
      debateManage: !!permissions.debateManage,
      judgeReview: !!permissions.judgeReview,
      judgeRejudge: !!permissions.judgeRejudge,
      roleManage: !!permissions.roleManage,
    },
  };
}

export function parseOpsPermissionDenied(rawText: unknown): OpsPermissionDenied | null {
  if (!rawText || typeof rawText !== 'string') {
    return null;
  }
  const text = rawText.trim();
  const prefix = 'ops_permission_denied:';
  if (!text.startsWith(prefix)) {
    return null;
  }

  const firstSep = text.indexOf(':');
  const secondSep = text.indexOf(':', firstSep + 1);
  if (secondSep <= firstSep + 1 || secondSep + 1 >= text.length) {
    return null;
  }

  const permission = text.slice(firstSep + 1, secondSep).trim();
  const reason = text.slice(secondSep + 1).trim();
  if (!permission || !reason) {
    return null;
  }
  return {
    permission,
    reason,
  };
}

export function getOpsPermissionHint(permission: string): string {
  return OPS_PERMISSION_HINTS[permission] || '当前账号没有执行该操作的权限';
}

export function hasOpsPermission(snapshot: OpsRbacMe | null | undefined, permission: OpsPermissionInputKey | string): boolean {
  const key = normalizePermissionKey(permission);
  if (!key) {
    return false;
  }
  return !!snapshot?.permissions?.[key];
}

export function hasAnyOpsPermission(snapshot: OpsRbacMe | null | undefined): boolean {
  return ['debateManage', 'judgeReview', 'judgeRejudge', 'roleManage']
    .some((key) => !!snapshot?.permissions?.[key as OpsPermissionKey]);
}

export function hasRequiredOpsPermissions(
  snapshot: OpsRbacMe | null | undefined,
  permissions: Array<OpsPermissionInputKey | string> = [],
): boolean {
  if (!Array.isArray(permissions) || permissions.length === 0) {
    return hasAnyOpsPermission(snapshot);
  }
  return permissions.every((item) => hasOpsPermission(snapshot, item));
}

type ErrorLike = {
  response?: {
    data?: {
      error?: unknown;
    };
  };
  message?: unknown;
};

export function resolveOpsErrorText(error: ErrorLike | null | undefined, fallback = '操作失败'): string {
  const serverText = error?.response?.data?.error;
  if (typeof serverText === 'string' && serverText.trim()) {
    const denied = parseOpsPermissionDenied(serverText);
    if (denied) {
      return `${getOpsPermissionHint(denied.permission)}（${denied.reason}）`;
    }
    return serverText;
  }
  if (typeof error?.message === 'string' && error.message.trim()) {
    return error.message;
  }
  return fallback;
}
