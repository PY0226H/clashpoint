export type SessionStatus =
  | 'scheduled'
  | 'open'
  | 'running'
  | 'judging'
  | 'closed'
  | 'canceled'
  | string;

export interface DebateTopicDTO {
  id: number;
  title: string;
  category?: string | null;
}

export interface DebateSessionDTO {
  id: number;
  topicId?: number | null;
  topic_id?: number | null;
  status?: SessionStatus | null;
  joinable?: boolean;
  scheduledStartAt?: string | null;
  endAt?: string | null;
  [key: string]: unknown;
}

export type LobbyLane = 'live' | 'upcoming' | 'ended' | 'unknown';
export type LobbyLaneFilter = LobbyLane | 'all';

export type OpsPermissionKey = 'debateManage' | 'judgeReview' | 'judgeRejudge' | 'roleManage';
export type OpsPermissionInputKey =
  | OpsPermissionKey
  | 'debate_manage'
  | 'judge_review'
  | 'judge_rejudge'
  | 'role_manage';

export interface OpsRbacPermissions {
  debateManage: boolean;
  judgeReview: boolean;
  judgeRejudge: boolean;
  roleManage: boolean;
}

export interface OpsRbacMe {
  userId: number;
  isOwner: boolean;
  role: string | null;
  permissions: OpsRbacPermissions;
}

export interface OpsPermissionDenied {
  permission: string;
  reason: string;
}

export interface AuthRefreshResponseDTO {
  accessToken: string;
}

export interface WalletBalanceResponseDTO {
  balance: number;
}

export interface ApiErrorPayloadDTO {
  error?: string;
}
