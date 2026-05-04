import type {
  DebateNpcFeedItem,
  DebateNpcState,
  DebateNpcStatus,
} from "./DebateNpcModel";

type DebateNpcPanelProps = {
  state: DebateNpcState;
};

type DebateNpcVisualProps = {
  effectKind: string | null;
  effectNonce: number;
  status: DebateNpcStatus;
};

type DebateNpcActionFeedProps = {
  items: DebateNpcFeedItem[];
};

const STATUS_LABEL: Record<DebateNpcStatus, string> = {
  observing: "Observing",
  speaking: "Speaking",
  praising: "Praising",
  silent: "Silent",
  unavailable: "Unavailable",
};

const ACTION_HEADLINE: Record<DebateNpcFeedItem["actionType"], string> = {
  speak: "Room comment",
  praise: "Highlighted move",
  effect: "Room effect",
  state_changed: "State update",
};

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

function DebateNpcActionFeed({ items }: DebateNpcActionFeedProps) {
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
          <div>
            <strong>{ACTION_HEADLINE[item.actionType]}</strong>
            <span>{formatNpcActionTime(item.createdAt)}</span>
          </div>
          <p>{item.text}</p>
          <small>{item.targetLabel}</small>
        </li>
      ))}
    </ol>
  );
}

export function DebateNpcPanel({ state }: DebateNpcPanelProps) {
  const latest = state.latestAction;

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

      <DebateNpcActionFeed items={state.feed} />
    </section>
  );
}
