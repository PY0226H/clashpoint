import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  requestNpcCoachAdvice,
  requestRoomQaAnswer,
  resolveJudgeAssistantAdvisoryView,
  toDebateDomainError,
  type DebateSide,
  type JudgeAssistantAdvisoryOutput,
  type JudgeAssistantAdvisoryView,
} from "@echoisle/debate-domain";
import { Button, InlineHint, TextField } from "@echoisle/ui";

type DebateAssistantPanelProps = {
  sessionId: number;
  caseId?: number | null;
  onHint?: (message: string) => void;
};

type AssistantAdvisoryResultProps = {
  title: string;
  view: JudgeAssistantAdvisoryView | null;
  errorMessage?: string | null;
};

function buildAssistantTraceId(
  agentKind: "npc_coach" | "room_qa",
  sessionId: number,
): string {
  return `debate_room_${agentKind}_${sessionId}_${Date.now()}`;
}

function normalizedCaseId(value: number | null | undefined): number | undefined {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return undefined;
  }
  return Math.floor(parsed);
}

export function AssistantAdvisoryResult({
  title,
  view,
  errorMessage,
}: AssistantAdvisoryResultProps) {
  const boundary = "辅助建议，不是官方裁决";
  if (errorMessage) {
    return (
      <div className="echo-assistant-result is-error">
        <h4>{title}</h4>
        <InlineHint>{boundary}</InlineHint>
        <p className="echo-error">{errorMessage}</p>
      </div>
    );
  }
  if (!view) {
    return (
      <div className="echo-assistant-result">
        <h4>{title}</h4>
        <InlineHint>{boundary}</InlineHint>
        <InlineHint>等待输入。</InlineHint>
      </div>
    );
  }
  return (
    <div className={`echo-assistant-result is-${view.state}`}>
      <h4>{title}</h4>
      <InlineHint>{boundary}</InlineHint>
      <InlineHint>
        {view.label} | {view.reasonCode}
      </InlineHint>
      <InlineHint>
        {view.contextLabel} | {view.receiptSummary}
      </InlineHint>
      {view.workflowStatus || view.latestDispatchType ? (
        <InlineHint>
          Workflow: {view.workflowStatus || "--"} | Dispatch:{" "}
          {view.latestDispatchType || "--"}
        </InlineHint>
      ) : null}
      {view.caseId ? <InlineHint>Case: #{view.caseId}</InlineHint> : null}
      {view.message ? <p>{view.message}</p> : null}
      {view.items.length > 0 ? (
        <ul className="echo-assistant-list">
          {view.items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function DebateAssistantPanel({
  sessionId,
  caseId,
  onHint,
}: DebateAssistantPanelProps) {
  const [npcQuery, setNpcQuery] = useState("我该怎么回应？");
  const [roomQaQuestion, setRoomQaQuestion] = useState("当前争点是什么？");
  const [npcSide, setNpcSide] = useState<DebateSide>("pro");
  const [npcResult, setNpcResult] =
    useState<JudgeAssistantAdvisoryOutput | null>(null);
  const [roomQaResult, setRoomQaResult] =
    useState<JudgeAssistantAdvisoryOutput | null>(null);
  const safeCaseId = normalizedCaseId(caseId);

  const npcMutation = useMutation({
    mutationFn: async () =>
      requestNpcCoachAdvice(sessionId, {
        query: npcQuery,
        traceId: buildAssistantTraceId("npc_coach", sessionId),
        side: npcSide,
        caseId: safeCaseId,
      }),
    onSuccess: (result) => {
      setNpcResult(result);
      onHint?.(resolveJudgeAssistantAdvisoryView(result).label);
    },
    onError: (error) => {
      onHint?.(toDebateDomainError(error));
    },
  });

  const roomQaMutation = useMutation({
    mutationFn: async () =>
      requestRoomQaAnswer(sessionId, {
        question: roomQaQuestion,
        traceId: buildAssistantTraceId("room_qa", sessionId),
        caseId: safeCaseId,
      }),
    onSuccess: (result) => {
      setRoomQaResult(result);
      onHint?.(resolveJudgeAssistantAdvisoryView(result).label);
    },
    onError: (error) => {
      onHint?.(toDebateDomainError(error));
    },
  });

  const npcView = useMemo(
    () => resolveJudgeAssistantAdvisoryView(npcResult),
    [npcResult],
  );
  const roomQaView = useMemo(
    () => resolveJudgeAssistantAdvisoryView(roomQaResult),
    [roomQaResult],
  );
  const sessionReady = Number.isFinite(sessionId) && sessionId > 0;

  return (
    <section className="echo-lobby-panel">
      <h3>辅助咨询</h3>
      {!safeCaseId ? (
        <InlineHint>暂无裁决上下文，将仅请求房间辅助入口。</InlineHint>
      ) : null}
      <div className="echo-assistant-grid">
        <div className="echo-assistant-tool">
          <h4>NPC Coach</h4>
          <div className="echo-assistant-segment" role="group" aria-label="选择立场">
            <Button
              className={npcSide === "pro" ? "is-active" : ""}
              onClick={() => setNpcSide("pro")}
              type="button"
            >
              正方
            </Button>
            <Button
              className={npcSide === "con" ? "is-active" : ""}
              onClick={() => setNpcSide("con")}
              type="button"
            >
              反方
            </Button>
          </div>
          <div className="echo-assistant-row">
            <TextField
              aria-label="NPC Coach query"
              onChange={(event) => setNpcQuery(event.target.value)}
              placeholder="我该怎么回应？"
              value={npcQuery}
            />
            <Button
              disabled={
                !sessionReady || npcMutation.isPending || !npcQuery.trim()
              }
              onClick={() => npcMutation.mutate()}
              type="button"
            >
              {npcMutation.isPending ? "请求中..." : "询问"}
            </Button>
          </div>
          <AssistantAdvisoryResult
            errorMessage={
              npcMutation.isError ? toDebateDomainError(npcMutation.error) : null
            }
            title="NPC Coach"
            view={npcResult ? npcView : null}
          />
        </div>

        <div className="echo-assistant-tool">
          <h4>Room QA</h4>
          <div className="echo-assistant-row">
            <TextField
              aria-label="Room QA question"
              onChange={(event) => setRoomQaQuestion(event.target.value)}
              placeholder="当前争点是什么？"
              value={roomQaQuestion}
            />
            <Button
              disabled={
                !sessionReady ||
                roomQaMutation.isPending ||
                !roomQaQuestion.trim()
              }
              onClick={() => roomQaMutation.mutate()}
              type="button"
            >
              {roomQaMutation.isPending ? "请求中..." : "提问"}
            </Button>
          </div>
          <AssistantAdvisoryResult
            errorMessage={
              roomQaMutation.isError
                ? toDebateDomainError(roomQaMutation.error)
                : null
            }
            title="Room QA"
            view={roomQaResult ? roomQaView : null}
          />
        </div>
      </div>
    </section>
  );
}
