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
  effectKind: string | null;
  effectNonce: number;
  status: DebateNpcStatus;
};

type DebateNpcActionFeedProps = {
  items: DebateNpcFeedItem[];
  feedbackPendingActionId?: number | null;
  onFeedback?: (actionId: number, feedbackType: DebateNpcFeedbackType) => void;
};

const STATUS_LABEL: Record<DebateNpcStatus, string> = {
  observing: "Observing",
  speaking: "Speaking",
  praising: "Praising",
  silent: "Silent",
  manual_takeover: "Manual",
  unavailable: "Unavailable",
};

const ACTION_HEADLINE: Record<DebateNpcFeedItem["actionType"], string> = {
  speak: "Room comment",
  praise: "Highlighted move",
  effect: "Room effect",
  state_changed: "State update",
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
  effectKind,
  effectNonce,
  status,
}: DebateNpcVisualProps) {
  return (
    <div className={`echo-npc-visual is-${status}`} aria-hidden="true">
      <div className="echo-npc-orbit" />
      <div className="echo-npc-avatar">
        <div className="echo-npc-avatar-face" />
        <div className="echo-npc-avatar-glow" />
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
        <li className="echo-npc-feed-item" key={item.actionUid}>
          <div className="echo-npc-feed-head">
            <strong>{ACTION_HEADLINE[item.actionType]}</strong>
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
    <section className={`echo-npc-panel is-${state.status}`} aria-live="polite">
      <header className="echo-npc-panel-header">
        <div>
          <p className="echo-npc-kicker">Room host</p>
          <h3>{state.displayName}</h3>
        </div>
        <span className="echo-npc-status">{STATUS_LABEL[state.status]}</span>
      </header>

      <div className="echo-npc-stage">
        <DebateNpcVisual
          effectKind={state.latestEffectKind}
          effectNonce={state.effectNonce}
          status={state.status}
        />
        <div className="echo-npc-latest">
          <strong>
            {latest ? ACTION_HEADLINE[latest.actionType] : "Live room pulse"}
          </strong>
          <p>
            {latest
              ? latest.text
              : "Ready to react when the debate turns lively."}
          </p>
          <span>{latest ? latest.targetLabel : "room"}</span>
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
