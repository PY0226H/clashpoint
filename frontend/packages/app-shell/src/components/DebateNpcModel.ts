import type {
  DebateNpcActionCreatedPayload,
  DebateNpcActionPublicItem,
  DebateNpcActionType,
} from "@echoisle/debate-domain";

export type DebateNpcStatus =
  | "observing"
  | "speaking"
  | "praising"
  | "silent"
  | "manual_takeover"
  | "unavailable";

export type DebateNpcFeedItem = {
  actionId: number;
  actionUid: string;
  actionType: DebateNpcActionType;
  displayName: string;
  text: string;
  targetLabel: string;
  effectKind: string | null;
  status: DebateNpcStatus;
  createdAt: string;
};

export type DebateNpcState = {
  displayName: string;
  status: DebateNpcStatus;
  latestAction: DebateNpcFeedItem | null;
  feed: DebateNpcFeedItem[];
  latestEffectKind: string | null;
  effectNonce: number;
  seenActionUids: string[];
};

export type DebateNpcReducerAction =
  | { type: "reset" }
  | { type: "history"; payload: DebateNpcActionPublicItem[] }
  | { type: "roomAction"; payload: DebateNpcActionCreatedPayload };

const MAX_NPC_FEED_ITEMS = 6;
const DEFAULT_NPC_DISPLAY_NAME = "Virtual Judge NPC";

export function createInitialDebateNpcState(): DebateNpcState {
  return {
    displayName: DEFAULT_NPC_DISPLAY_NAME,
    status: "observing",
    latestAction: null,
    feed: [],
    latestEffectKind: null,
    effectNonce: 0,
    seenActionUids: [],
  };
}

function normalizeNpcStatus(
  value: string | null | undefined,
): DebateNpcStatus | null {
  switch ((value || "").trim().toLowerCase()) {
    case "observing":
      return "observing";
    case "speaking":
      return "speaking";
    case "praising":
      return "praising";
    case "silent":
      return "silent";
    case "manual_takeover":
      return "manual_takeover";
    case "unavailable":
      return "unavailable";
    default:
      return null;
  }
}

type DebateNpcVisibleAction =
  | DebateNpcActionCreatedPayload
  | DebateNpcActionPublicItem;

export function resolveDebateNpcStatus(
  action: DebateNpcVisibleAction,
): DebateNpcStatus {
  const explicitStatus = normalizeNpcStatus(action.npcStatus);
  if (explicitStatus) {
    return explicitStatus;
  }

  switch (action.actionType) {
    case "speak":
      return "speaking";
    case "praise":
      return "praising";
    case "pause_suggestion":
      return "speaking";
    case "state_changed":
      return "observing";
    case "effect":
      return "observing";
    default:
      return "observing";
  }
}

function resolveDebateNpcText(action: DebateNpcVisibleAction): string {
  const text = action.publicText?.trim();
  if (text) {
    return text;
  }

  switch (action.actionType) {
    case "praise":
      return "Marked a strong turn in the argument.";
    case "speak":
      return "Shared a room-wide comment.";
    case "effect":
      return "Sent a short room effect.";
    case "pause_suggestion":
      return "Suggested a brief pause review.";
    case "state_changed":
      return "Shifted back into observation.";
    default:
      return "Watching the room.";
  }
}

export function resolveDebateNpcTargetLabel(
  action: DebateNpcVisibleAction,
): string {
  const parts: string[] = [];
  if (action.targetMessageId != null) {
    parts.push(`message #${action.targetMessageId}`);
  }
  if (action.targetSide) {
    parts.push(action.targetSide.toUpperCase());
  }
  if (action.targetUserId != null) {
    parts.push(`user ${action.targetUserId}`);
  }
  return parts.length > 0 ? parts.join(" / ") : "room";
}

export function buildDebateNpcFeedItem(
  action: DebateNpcVisibleAction,
): DebateNpcFeedItem {
  return {
    actionId: action.actionId,
    actionUid: action.actionUid,
    actionType: action.actionType,
    displayName: action.displayName,
    text: resolveDebateNpcText(action),
    targetLabel: resolveDebateNpcTargetLabel(action),
    effectKind: action.effectKind?.trim() || null,
    status: resolveDebateNpcStatus(action),
    createdAt: action.createdAt,
  };
}

export function debateNpcReducer(
  state: DebateNpcState,
  action: DebateNpcReducerAction,
): DebateNpcState {
  if (action.type === "reset") {
    return createInitialDebateNpcState();
  }

  if (action.type === "history") {
    const items = action.payload.map(buildDebateNpcFeedItem);
    const feed = items.slice(0, MAX_NPC_FEED_ITEMS);
    const latest = feed[0] || null;
    return {
      displayName: latest?.displayName || state.displayName,
      status: latest?.status || state.status,
      latestAction: latest,
      feed,
      latestEffectKind: latest?.effectKind || state.latestEffectKind,
      effectNonce: state.effectNonce,
      seenActionUids: items.map((item) => item.actionUid).slice(0, 80),
    };
  }

  if (state.seenActionUids.includes(action.payload.actionUid)) {
    return state;
  }

  const item = buildDebateNpcFeedItem(action.payload);
  const nextSeen = [item.actionUid, ...state.seenActionUids].slice(0, 80);
  const nextFeed = [item, ...state.feed]
    .filter(
      (entry, index, entries) =>
        entries.findIndex(
          (candidate) => candidate.actionUid === entry.actionUid,
        ) === index,
    )
    .slice(0, MAX_NPC_FEED_ITEMS);

  return {
    displayName: item.displayName,
    status: item.status,
    latestAction: item,
    feed: nextFeed,
    latestEffectKind: item.effectKind,
    effectNonce: state.effectNonce + 1,
    seenActionUids: nextSeen,
  };
}
