import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  requestDebateAssistant,
  requestDebateAssistantStatus,
  resolveDebateAssistantView,
  toDebateDomainError,
  type DebateAssistantIntent,
  type DebateAssistantOutput,
  type DebateAssistantStatusOutput,
  type DebateAssistantView,
  type DebateSide,
} from "@echoisle/debate-domain";
import { Button, InlineHint } from "@echoisle/ui";

type DebateAssistantPanelProps = {
  sessionId: number;
  caseId?: number | null;
  viewerRole?: string | null;
  viewerSide?: DebateSide | null | string;
  canSendMessage?: boolean;
  onHint?: (message: string) => void;
};

type AssistantIntentPreset = {
  intent: DebateAssistantIntent;
  label: string;
  question: string;
  requiresDraft?: boolean;
};

type DebateAssistantResultProps = {
  view: DebateAssistantView | null;
  errorMessage?: string | null;
};

type DebateAssistantLockStateProps = {
  status?: DebateAssistantStatusOutput | null;
  reason?: string | null;
};

const ASSISTANT_INTENT_PRESETS: AssistantIntentPreset[] = [
  {
    intent: "room_summary",
    label: "总结争点",
    question: "请总结当前房间最重要的争点。",
  },
  {
    intent: "opponent_summary",
    label: "对方观点",
    question: "请概括对方最近主要在说什么。",
  },
  {
    intent: "unanswered_points",
    label: "待回应点",
    question: "请指出我方还没有回应充分的点。",
  },
  {
    intent: "speech_structure",
    label: "发言结构",
    question: "请给我一个下一段发言结构。",
  },
  {
    intent: "draft_polish",
    label: "优化草稿",
    question: "请帮我优化这段草稿，但不要改变我的立场。",
    requiresDraft: true,
  },
];

function buildAssistantTraceId(sessionId: number): string {
  return `debate_room_debate_assistant_${sessionId}_${Date.now()}`;
}

function normalizedCaseId(value: number | null | undefined): number | undefined {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return Math.floor(parsed);
}

function normalizedPanelSide(
  value: DebateSide | string | null | undefined,
): DebateSide | undefined {
  return value === "pro" || value === "con" ? value : undefined;
}

function quotaSummary(status?: DebateAssistantStatusOutput | null): string {
  if (!status) {
    return "额度未加载";
  }
  return `本场剩余 ${status.quota.remaining}/${status.quota.limit}`;
}

export function DebateAssistantLockState({
  status,
  reason,
}: DebateAssistantLockStateProps) {
  const message =
    reason ||
    (status?.membership.active === false
      ? "开通会员后可在参赛房间使用私人辩论助手。"
      : status?.quota.remaining === 0
        ? "本场助手额度已经用完。"
        : "当前暂不可使用辩论助手。");
  return (
    <div className="echo-assistant-result is-locked">
      <h4>会员专属</h4>
      <InlineHint>{status?.boundaryNotice || "私人辅助，不是官方裁决。"}</InlineHint>
      <p>{message}</p>
      {status ? <InlineHint>{quotaSummary(status)}</InlineHint> : null}
    </div>
  );
}

function AssistantSection({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div>
      <h5>{title}</h5>
      <ul className="echo-assistant-list">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function DebateAssistantResult({
  view,
  errorMessage,
}: DebateAssistantResultProps) {
  if (errorMessage) {
    return (
      <div className="echo-assistant-result is-error">
        <h4>助手回复</h4>
        <InlineHint>私人辅助，不是官方裁决。</InlineHint>
        <p className="echo-error">{errorMessage}</p>
      </div>
    );
  }
  if (!view) {
    return (
      <div className="echo-assistant-result">
        <h4>助手回复</h4>
        <InlineHint>私人辅助，不是官方裁决。</InlineHint>
        <InlineHint>选择一个问题或输入你的问题。</InlineHint>
      </div>
    );
  }
  return (
    <div className={`echo-assistant-result is-${view.state}`}>
      <h4>助手回复</h4>
      <InlineHint>{view.boundaryNotice}</InlineHint>
      <InlineHint>
        {view.label} | {view.reasonCode}
      </InlineHint>
      {view.answerSummary ? <p>{view.answerSummary}</p> : null}
      <AssistantSection items={view.keyPoints} title="要点" />
      <AssistantSection items={view.suggestedActions} title="行动建议" />
      <AssistantSection items={view.contextCaveats} title="不确定性提示" />
      {view.sourceUsePolicy ? (
        <InlineHint>{view.sourceUsePolicy}</InlineHint>
      ) : null}
    </div>
  );
}

export function DebateAssistantPanel({
  sessionId,
  caseId,
  viewerRole,
  viewerSide,
  canSendMessage,
  onHint,
}: DebateAssistantPanelProps) {
  const queryClient = useQueryClient();
  const [intent, setIntent] = useState<DebateAssistantIntent>("room_summary");
  const [question, setQuestion] = useState(
    ASSISTANT_INTENT_PRESETS[0].question,
  );
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState<DebateAssistantOutput | null>(null);
  const safeCaseId = normalizedCaseId(caseId);
  const sessionReady = Number.isFinite(sessionId) && sessionId > 0;

  const statusQuery = useQuery({
    queryKey: ["debate-assistant-status", sessionId],
    queryFn: () => requestDebateAssistantStatus(sessionId),
    enabled: sessionReady,
  });

  const selectedPreset = useMemo(
    () =>
      ASSISTANT_INTENT_PRESETS.find((preset) => preset.intent === intent) ||
      ASSISTANT_INTENT_PRESETS[0],
    [intent],
  );
  const resultView = useMemo(
    () => resolveDebateAssistantView(result),
    [result],
  );
  const status = statusQuery.data;
  const statusIntents = new Set(status?.intents || []);
  const statusAllowsIntent =
    statusIntents.size === 0 || statusIntents.has(intent);
  const panelViewerRole = String(
    status?.viewerRole || viewerRole || "participant",
  );
  const panelCanSendMessage = canSendMessage ?? panelViewerRole === "participant";
  const participantLocked =
    panelViewerRole === "spectator" || panelCanSendMessage === false;
  const membershipLocked = status ? !status.membership.active : false;
  const quotaLocked = status ? status.quota.remaining <= 0 : false;
  const assistantAvailable =
    Boolean(status?.available) &&
    !participantLocked &&
    !membershipLocked &&
    !quotaLocked;
  const needsDraft = selectedPreset.requiresDraft === true;
  const queryDisabled =
    !sessionReady ||
    !assistantAvailable ||
    !statusAllowsIntent ||
    !question.trim() ||
    (needsDraft && !draft.trim());

  const assistantMutation = useMutation({
    mutationFn: async () =>
      requestDebateAssistant(sessionId, {
        intent,
        question,
        draft: needsDraft ? draft : undefined,
        traceId: buildAssistantTraceId(sessionId),
        side: normalizedPanelSide(status?.viewerSide || viewerSide),
        caseId: safeCaseId,
      }),
    onSuccess: (nextResult) => {
      setResult(nextResult);
      const view = resolveDebateAssistantView(nextResult);
      onHint?.(view.label);
      if (nextResult.accepted) {
        void queryClient.invalidateQueries({
          queryKey: ["debate-assistant-status", sessionId],
        });
      }
    },
    onError: (error) => {
      onHint?.(toDebateDomainError(error));
    },
  });

  function choosePreset(preset: AssistantIntentPreset): void {
    setIntent(preset.intent);
    setQuestion(preset.question);
  }

  const lockReason = participantLocked
    ? "当前 MVP 仅支持参赛用户使用私人辩论助手。"
    : membershipLocked
      ? "开通会员后可在参赛房间使用私人辩论助手。"
      : quotaLocked
        ? "本场助手额度已经用完。"
        : null;

  return (
    <section className="echo-lobby-panel">
      <div className="echo-assistant-header">
        <div>
          <h3>辩论助手</h3>
          <InlineHint>
            {status?.boundaryNotice || "私人辅助，不是官方裁决；不会自动发送公开发言。"}
          </InlineHint>
        </div>
        <InlineHint>{quotaSummary(status)}</InlineHint>
      </div>

      {statusQuery.isLoading ? <InlineHint>正在加载助手状态...</InlineHint> : null}
      {statusQuery.isError ? (
        <p className="echo-error">{toDebateDomainError(statusQuery.error)}</p>
      ) : null}

      {lockReason ? (
        <DebateAssistantLockState reason={lockReason} status={status} />
      ) : null}

      <div className="echo-assistant-grid is-single">
        <div className="echo-assistant-tool">
          <div
            className="echo-assistant-segment"
            role="group"
            aria-label="选择辩论助手问题"
          >
            {ASSISTANT_INTENT_PRESETS.map((preset) => (
              <Button
                className={intent === preset.intent ? "is-active" : ""}
                disabled={!assistantAvailable || assistantMutation.isPending}
                key={preset.intent}
                onClick={() => choosePreset(preset)}
                type="button"
              >
                {preset.label}
              </Button>
            ))}
          </div>
          <textarea
            aria-label="辩论助手问题"
            className="echo-input echo-assistant-textarea"
            disabled={!assistantAvailable || assistantMutation.isPending}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="输入你想问助手的问题"
            value={question}
          />
          {needsDraft ? (
            <textarea
              aria-label="待优化草稿"
              className="echo-input echo-assistant-textarea"
              disabled={!assistantAvailable || assistantMutation.isPending}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="粘贴你的草稿，助手只会在面板内给出优化建议"
              value={draft}
            />
          ) : null}
          {!statusAllowsIntent ? (
            <InlineHint>当前房间暂不支持这个助手问题。</InlineHint>
          ) : null}
          <div className="echo-assistant-actions">
            <Button
              disabled={queryDisabled || assistantMutation.isPending}
              onClick={() => assistantMutation.mutate()}
              type="button"
            >
              {assistantMutation.isPending ? "请求中..." : "询问助手"}
            </Button>
          </div>
        </div>

        <DebateAssistantResult
          errorMessage={
            assistantMutation.isError
              ? toDebateDomainError(assistantMutation.error)
              : null
          }
          view={result ? resultView : null}
        />
      </div>
    </section>
  );
}
