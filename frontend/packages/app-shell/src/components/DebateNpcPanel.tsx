import { useState, type FormEvent } from "react";
import type {
  DebateNpcFeedbackType,
  DebateNpcPublicCallType,
} from "@echoisle/debate-domain";
import type {
  DebateNpcFeedItem,
  DebateNpcState,
  DebateNpcStatus,
} from "./DebateNpcModel";

type DebateNpcPanelProps = {
  state: DebateNpcState;
  canPublicCall?: boolean;
  publicCallPending?: boolean;
  feedbackPendingActionId?: number | null;
  onPublicCall?: (input: {
    callType: DebateNpcPublicCallType;
    content: string;
  }) => void;
  onFeedback?: (actionId: number, feedbackType: DebateNpcFeedbackType) => void;
};

type DebateNpcVisualProps = {
  actionType: DebateNpcFeedItem["actionType"] | null;
  effectKind: string | null;
  effectNonce: number;
  status: DebateNpcStatus;
};

type DebateNpcActionFeedProps = {
  items: DebateNpcFeedItem[];
  feedbackPendingActionId?: number | null;
  onFeedback?: (actionId: number, feedbackType: DebateNpcFeedbackType) => void;
};

const STATUS_META: Record<
  DebateNpcStatus,
  {
    label: string;
    summary: string;
  }
> = {
  observing: {
    label: "Watching",
    summary: "Tracking the room rhythm.",
  },
  speaking: {
    label: "On mic",
    summary: "Sharing a public room cue.",
  },
  praising: {
    label: "Cheering",
    summary: "Spotlighting a strong turn.",
  },
  silent: {
    label: "Quiet",
    summary: "Holding the stage back.",
  },
  manual_takeover: {
    label: "Manual",
    summary: "Ops is steering the host.",
  },
  unavailable: {
    label: "Offline",
    summary: "Room host is unavailable.",
  },
};

const ACTION_META: Record<
  DebateNpcFeedItem["actionType"],
  {
    headline: string;
    intensity: "low" | "medium" | "high";
  }
> = {
  speak: {
    headline: "Room comment",
    intensity: "medium",
  },
  praise: {
    headline: "Highlighted move",
    intensity: "high",
  },
  effect: {
    headline: "Room effect",
    intensity: "high",
  },
  pause_suggestion: {
    headline: "Pause suggestion",
    intensity: "medium",
  },
  state_changed: {
    headline: "State update",
    intensity: "low",
  },
};

const PUBLIC_CALL_OPTIONS: Array<{
  value: DebateNpcPublicCallType;
  label: string;
}> = [
  { value: "issue_summary", label: "Summarize" },
  { value: "rules_help", label: "Rules" },
  { value: "pause_review", label: "Pause" },
  { value: "report_issue", label: "Report" },
  { value: "atmosphere_effect", label: "Effect" },
];

const FEEDBACK_OPTIONS: Array<{
  value: DebateNpcFeedbackType;
  label: string;
}> = [
  { value: "helpful", label: "Helpful" },
  { value: "too_disruptive", label: "Too much" },
  { value: "not_neutral", label: "Bias?" },
  { value: "confusing", label: "Confusing" },
];

function formatNpcActionTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function DebateNpcVisual({
  actionType,
  effectKind,
  effectNonce,
  status,
}: DebateNpcVisualProps) {
  const intensity = actionType ? ACTION_META[actionType].intensity : "low";
  return (
    <div
      className={`echo-npc-visual is-${status} is-action-${actionType || "idle"}`}
      aria-hidden="true"
      data-action-intensity={intensity}
      data-effect-kind={effectKind || "none"}
    >
      <div className="echo-npc-stage-rings">
        <span />
        <span />
      </div>
      <div className="echo-npc-avatar" data-effect-kind={effectKind || "none"}>
        <div className="echo-npc-avatar-band" />
        <div className="echo-npc-avatar-eyes">
          <span />
          <span />
        </div>
        <div className="echo-npc-avatar-mouth" />
        <div className="echo-npc-avatar-glow" />
      </div>
      <div className="echo-npc-signal-bars">
        <span />
        <span />
        <span />
      </div>
      <div
        className="echo-npc-effect-burst"
        data-effect-kind={effectKind || "none"}
        key={`${effectNonce}-${effectKind || "idle"}`}
      />
    </div>
  );
}

function DebateNpcActionFeed({
  feedbackPendingActionId,
  items,
  onFeedback,
}: DebateNpcActionFeedProps) {
  if (items.length === 0) {
    return (
      <div className="echo-npc-feed-empty">
        <span>Watching the room.</span>
      </div>
    );
  }

  return (
    <ol className="echo-npc-feed">
      {items.map((item) => (
        <li
          className={`echo-npc-feed-item is-action-${item.actionType}`}
          key={item.actionUid}
        >
          <div className="echo-npc-feed-head">
            <strong>{ACTION_META[item.actionType].headline}</strong>
            <span>{formatNpcActionTime(item.createdAt)}</span>
          </div>
          <p>{item.text}</p>
          <small>{item.targetLabel}</small>
          {onFeedback ? (
            <div className="echo-npc-feedback">
              {FEEDBACK_OPTIONS.map((option) => (
                <button
                  disabled={feedbackPendingActionId === item.actionId}
                  key={option.value}
                  onClick={() => onFeedback(item.actionId, option.value)}
                  type="button"
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

export function DebateNpcPanel({
  canPublicCall = false,
  feedbackPendingActionId = null,
  onFeedback,
  onPublicCall,
  publicCallPending = false,
  state,
}: DebateNpcPanelProps) {
  const latest = state.latestAction;
  const latestActionType = latest?.actionType || null;
  const latestActionMeta = latestActionType
    ? ACTION_META[latestActionType]
    : null;
  const statusMeta = STATUS_META[state.status];
  const [callType, setCallType] =
    useState<DebateNpcPublicCallType>("issue_summary");
  const [content, setContent] = useState("");
  const normalizedContent = content.trim();

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!normalizedContent || !canPublicCall || !onPublicCall) {
      return;
    }
    onPublicCall({ callType, content: normalizedContent });
    setContent("");
  }

  return (
    <section
      className={`echo-npc-panel is-${state.status} is-action-${
        latestActionType || "idle"
      }`}
      aria-label={`${state.displayName} live room NPC`}
      aria-live="polite"
      data-action-intensity={latestActionMeta?.intensity || "low"}
    >
      <header className="echo-npc-panel-header">
        <div>
          <p className="echo-npc-kicker">Room host</p>
          <h3>{state.displayName}</h3>
        </div>
        <div className="echo-npc-status-block">
          <span className="echo-npc-boundary">Live NPC</span>
          <span className="echo-npc-status">{statusMeta.label}</span>
        </div>
      </header>

      <div className="echo-npc-stage">
        <DebateNpcVisual
          actionType={latestActionType}
          effectKind={state.latestEffectKind}
          effectNonce={state.effectNonce}
          status={state.status}
        />
        <div className="echo-npc-latest">
          <strong>
            {latest
              ? ACTION_META[latest.actionType].headline
              : "Live room pulse"}
          </strong>
          <p>
            {latest
              ? latest.text
              : "Ready to react when the debate turns lively."}
          </p>
          <span>{latest ? latest.targetLabel : statusMeta.summary}</span>
        </div>
      </div>

      <form className="echo-npc-call" onSubmit={handleSubmit}>
        <select
          disabled={!canPublicCall || publicCallPending}
          onChange={(event) =>
            setCallType(event.target.value as DebateNpcPublicCallType)
          }
          value={callType}
        >
          {PUBLIC_CALL_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          disabled={!canPublicCall || publicCallPending}
          maxLength={500}
          onChange={(event) => setContent(event.target.value)}
          placeholder={
            canPublicCall
              ? "Call the NPC in public..."
              : "Public calls are unavailable"
          }
          value={content}
        />
        <button
          disabled={!canPublicCall || !normalizedContent || publicCallPending}
          type="submit"
        >
          {publicCallPending ? "Calling..." : "Call"}
        </button>
      </form>

      <DebateNpcActionFeed
        feedbackPendingActionId={feedbackPendingActionId}
        items={state.feed}
        onFeedback={onFeedback}
      />
    </section>
  );
}
