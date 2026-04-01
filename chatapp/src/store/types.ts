import type { OpsRbacMe } from '../types/api';

export interface AuthUserProfile {
  id?: number;
  email?: string | null;
  phoneE164?: string | null;
  phoneBindRequired?: boolean;
  [key: string]: unknown;
}

export interface RootGettersSnapshot {
  getUser?: AuthUserProfile | null;
  getOpsRbacMe?: OpsRbacMe | null;
  [key: string]: unknown;
}
