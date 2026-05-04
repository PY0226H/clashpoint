import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@echoisle/auth-sdk";
import { getRuntimeConfig } from "@echoisle/config";
import {
  createDebateMessage,
  getDebateDrawVoteStatus,
  getDebateJudgeChallenge,
  getDebateJudgePublicVerification,
  getDebateJudgeReport,
  getOldestDebateMessageId,
  getWalletBalance,
  isDebateNpcActionCreatedPayload,
  listDebateMessages,
  listDebatePinnedMessages,
  mergeDebateMessages,
  pinDebateMessage,
  requestDebateJudgeChallenge,
  requestDebateJudgeJob,
  resolveDebateJudgeChallengeView,
  resolveDebateJudgePublicVerificationView,
  submitDebateDrawVote,
  toDebateDomainError,
  type DebateMessage,
} from "@echoisle/debate-domain";
import {
  buildDebateRoomAckMessage,
  buildDebateRoomClientMessage,
  buildDebateRoomWsUrl,
  buildNotifyTicketProtocol,
  computeWsReconnectDelayMs,
  parseDebateRoomServerMessage,
} from "@echoisle/realtime-sdk";
import { Button, InlineHint, SectionTitle, TextField } from "@echoisle/ui";
import { useNavigate, useParams } from "react-router-dom";
import { DebateAssistantPanel } from "../components/DebateAssistantPanel";
import { DebateNpcPanel } from "../components/DebateNpcPanel";
import {
  debateNpcReducer,
  createInitialDebateNpcState,
} from "../components/DebateNpcModel";

const runtime = getRuntimeConfig();
const HISTORY_LIMIT = 80;
const PINS_LIMIT = 20;

function formatUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString();
}

function formatPublicHash(value: string): string {
  const trimmed = value.trim();
  if (trimmed.length <= 44) {
    return trimmed;
  }
  return `${trimmed.slice(0, 24)}...${trimmed.slice(-12)}`;
}

function toRoomMessage(payload: Record<string, unknown>): DebateMessage | null {
  const id = Number(payload.messageId ?? payload.id);
  if (!Number.isFinite(id) || id <= 0) {
    return null;
  }
  return {
    id,
    sessionId: Number(payload.sessionId || 0),
    userId: Number(payload.userId || 0),
    side: String(payload.side || "unknown"),
    content: String(payload.content || ""),
    createdAt: String(payload.createdAt || new Date().toISOString()),
  };
}

export function DebateRoomPage() {
  const navigate = useNavigate();
  const { sessionId } = useParams();
  const sessionIdNum = Number(sessionId);
  const queryClient = useQueryClient();
  const notifyTicket = useAuthStore(
    (state) => state.accessTickets?.notifyToken || null,
  );
  const refreshAccessTickets = useAuthStore(
    (state) => state.refreshAccessTickets,
  );
  const [messages, setMessages] = useState<DebateMessage[]>([]);
  const [hasMoreHistory, setHasMoreHistory] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [messageInput, setMessageInput] = useState("");
  const [pinSecondsInput, setPinSecondsInput] = useState("60");
  const [pageHint, setPageHint] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<
    "disconnected" | "connecting" | "connected" | "reconnecting"
  >("disconnected");
  const [npcState, dispatchNpcState] = useReducer(
    debateNpcReducer,
    undefined,
    createInitialDebateNpcState,
  );
  const wsRef = useRef<WebSocket | null>(null);
  const connectWsRef = useRef<() => void>(() => undefined);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const lastAckSeqRef = useRef(0);
  const closedRef = useRef(false);

  const messagesQuery = useQuery({
    queryKey: ["debate-room-messages", sessionIdNum],
    queryFn: () => listDebateMessages(sessionIdNum, { limit: HISTORY_LIMIT }),
    enabled: Number.isFinite(sessionIdNum) && sessionIdNum > 0,
  });

  const pinsQuery = useQuery({
    queryKey: ["debate-room-pins", sessionIdNum],
    queryFn: () =>
      listDebatePinnedMessages(sessionIdNum, {
        activeOnly: true,
        limit: PINS_LIMIT,
      }),
    enabled: Number.isFinite(sessionIdNum) && sessionIdNum > 0,
  });

  const walletQuery = useQuery({
    queryKey: ["wallet-balance"],
    queryFn: () => getWalletBalance(),
  });

  const judgeReportQuery = useQuery({
    queryKey: ["debate-room-judge-report", sessionIdNum],
    queryFn: () => getDebateJudgeReport(sessionIdNum),
    enabled: Number.isFinite(sessionIdNum) && sessionIdNum > 0,
  });

  const judgePublicVerificationQuery = useQuery({
    queryKey: ["debate-room-judge-public-verification", sessionIdNum],
    queryFn: () =>
      getDebateJudgePublicVerification(sessionIdNum, { dispatchType: "final" }),
    enabled: Number.isFinite(sessionIdNum) && sessionIdNum > 0,
  });

  const judgeChallengeQuery = useQuery({
    queryKey: ["debate-room-judge-challenge", sessionIdNum],
    queryFn: () => getDebateJudgeChallenge(sessionIdNum, { dispatchType: "final" }),
    enabled: Number.isFinite(sessionIdNum) && sessionIdNum > 0,
  });

  const drawVoteQuery = useQuery({
    queryKey: ["debate-room-draw-vote", sessionIdNum],
    queryFn: () => getDebateDrawVoteStatus(sessionIdNum),
    enabled: Number.isFinite(sessionIdNum) && sessionIdNum > 0,
  });

  const sendMutation = useMutation({
    mutationFn: async (content: string) =>
      createDebateMessage(sessionIdNum, content),
    onSuccess: (created) => {
      setMessageInput("");
      setPageHint("Message sent.");
      setMessages((current) => mergeDebateMessages(current, [created]));
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-messages", sessionIdNum],
      });
    },
    onError: (error) => {
      setPageHint(toDebateDomainError(error));
    },
  });

  const requestJudgeMutation = useMutation({
    mutationFn: async () =>
      requestDebateJudgeJob(sessionIdNum, { allowRejudge: false }),
    onSuccess: (result) => {
      setPageHint(
        `Judge request accepted (${result.status}), phaseJobs=${result.queuedPhaseJobs}, finalJob=${String(result.queuedFinalJob)}`,
      );
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-report", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-public-verification", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-challenge", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-draw-vote", sessionIdNum],
      });
      void queryClient.invalidateQueries({ queryKey: ["debate-sessions"] });
    },
    onError: (error) => {
      setPageHint(toDebateDomainError(error));
    },
  });

  const requestJudgeChallengeMutation = useMutation({
    mutationFn: async () =>
      requestDebateJudgeChallenge(sessionIdNum, {
        dispatchType: "final",
        reasonCode: "manual_challenge",
      }),
    onSuccess: (result) => {
      const view = resolveDebateJudgeChallengeView(result);
      setPageHint(view.label);
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-challenge", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-report", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-public-verification", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-challenge", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-draw-vote", sessionIdNum],
      });
      void queryClient.invalidateQueries({ queryKey: ["debate-sessions"] });
    },
    onError: (error) => {
      setPageHint(toDebateDomainError(error));
    },
  });

  const drawVoteMutation = useMutation({
    mutationFn: async (agreeDraw: boolean) =>
      submitDebateDrawVote(sessionIdNum, agreeDraw),
    onSuccess: (result, agreeDraw) => {
      setPageHint(
        agreeDraw
          ? `Draw vote submitted: agree (${result.vote.agreeVotes}/${result.vote.requiredVoters})`
          : `Draw vote submitted: disagree (${result.vote.disagreeVotes}/${result.vote.requiredVoters})`,
      );
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-draw-vote", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-report", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-public-verification", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-challenge", sessionIdNum],
      });
      void queryClient.invalidateQueries({ queryKey: ["debate-sessions"] });
    },
    onError: (error) => {
      setPageHint(toDebateDomainError(error));
    },
  });

  const pinMutation = useMutation({
    mutationFn: async (payload: { messageId: number; pinSeconds: number }) =>
      pinDebateMessage(payload.messageId, payload.pinSeconds),
    onSuccess: (result) => {
      setPageHint(
        `Pinned message #${result.messageId}: -${result.debitedCoins} coins, balance=${result.walletBalance}, expires=${formatUtc(result.expiresAt)}`,
      );
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-pins", sessionIdNum],
      });
      void queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-messages", sessionIdNum],
      });
    },
    onError: (error) => {
      setPageHint(toDebateDomainError(error));
    },
  });

  useEffect(() => {
    if (!messagesQuery.data) {
      return;
    }
    setMessages((current) =>
      mergeDebateMessages(current, messagesQuery.data.items),
    );
    setHasMoreHistory(Boolean(messagesQuery.data.hasMore));
  }, [messagesQuery.data]);

  useEffect(() => {
    setMessages([]);
    setHasMoreHistory(true);
    setPageHint(null);
    dispatchNpcState({ type: "reset" });
    lastAckSeqRef.current = 0;
  }, [sessionIdNum]);

  useEffect(() => {
    if (!Number.isFinite(sessionIdNum) || sessionIdNum <= 0) {
      return;
    }
    void refreshAccessTickets().catch(() => undefined);
  }, [refreshAccessTickets, sessionIdNum]);

  const scheduleReconnect = useCallback(() => {
    if (closedRef.current || reconnectTimerRef.current) {
      return;
    }
    reconnectAttemptRef.current += 1;
    setWsStatus("reconnecting");
    const delay = computeWsReconnectDelayMs(reconnectAttemptRef.current);
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-messages", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-pins", sessionIdNum],
      });
      void queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-report", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-public-verification", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-judge-challenge", sessionIdNum],
      });
      void queryClient.invalidateQueries({
        queryKey: ["debate-room-draw-vote", sessionIdNum],
      });
      connectWsRef.current();
    }, delay);
  }, [queryClient, sessionIdNum]);

  const cleanupWs = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const handleRoomPayload = useCallback(
    (payload: Record<string, unknown>) => {
      const event = String(payload.event || "");
      if (isDebateNpcActionCreatedPayload(payload)) {
        dispatchNpcState({ type: "roomAction", payload });
        return;
      }
      if (event === "DebateMessageCreated") {
        const roomMessage = toRoomMessage(payload);
        if (roomMessage) {
          setMessages((current) => mergeDebateMessages(current, [roomMessage]));
        }
        return;
      }
      if (event === "DebateMessagePinned") {
        void queryClient.invalidateQueries({
          queryKey: ["debate-room-pins", sessionIdNum],
        });
        void queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
        return;
      }
      if (
        event.includes("Judge") ||
        event.includes("DrawVote") ||
        event.includes("Rematch") ||
        event.includes("DebateSession")
      ) {
        void queryClient.invalidateQueries({
          queryKey: ["debate-room-judge-report", sessionIdNum],
        });
        void queryClient.invalidateQueries({
          queryKey: ["debate-room-judge-public-verification", sessionIdNum],
        });
        void queryClient.invalidateQueries({
          queryKey: ["debate-room-judge-challenge", sessionIdNum],
        });
        void queryClient.invalidateQueries({
          queryKey: ["debate-room-draw-vote", sessionIdNum],
        });
        void queryClient.invalidateQueries({ queryKey: ["debate-sessions"] });
      }
    },
    [queryClient, sessionIdNum],
  );

  const connectWs = useCallback(() => {
    if (
      closedRef.current ||
      !notifyTicket ||
      !Number.isFinite(sessionIdNum) ||
      sessionIdNum <= 0
    ) {
      return;
    }
    setWsStatus("connecting");
    try {
      const url = buildDebateRoomWsUrl({
        notifyBase: runtime.server.notification,
        sessionId: sessionIdNum,
        lastAckSeq: lastAckSeqRef.current,
      });
      const protocol = buildNotifyTicketProtocol(notifyTicket);
      const ws = new WebSocket(url, [protocol]);
      wsRef.current = ws;
      ws.onopen = () => {
        reconnectAttemptRef.current = 0;
        setWsStatus("connected");
      };
      ws.onmessage = (event) => {
        const msg = parseDebateRoomServerMessage(String(event.data || ""));
        if (!msg) {
          return;
        }
        if (msg.type === "ping") {
          ws.send(buildDebateRoomClientMessage({ type: "pong" }));
          return;
        }
        if (msg.type === "welcome") {
          lastAckSeqRef.current = Math.max(
            lastAckSeqRef.current,
            msg.baselineAckSeq,
          );
          return;
        }
        if (msg.type === "syncRequired") {
          setPageHint(`Realtime sync required: ${msg.reason}`);
          lastAckSeqRef.current = Math.max(
            lastAckSeqRef.current,
            msg.suggestedLastAckSeq,
          );
          void queryClient.invalidateQueries({
            queryKey: ["debate-room-messages", sessionIdNum],
          });
          void queryClient.invalidateQueries({
            queryKey: ["debate-room-pins", sessionIdNum],
          });
          void queryClient.invalidateQueries({ queryKey: ["wallet-balance"] });
          void queryClient.invalidateQueries({
            queryKey: ["debate-room-judge-report", sessionIdNum],
          });
          void queryClient.invalidateQueries({
            queryKey: ["debate-room-judge-public-verification", sessionIdNum],
          });
          void queryClient.invalidateQueries({
            queryKey: ["debate-room-judge-challenge", sessionIdNum],
          });
          void queryClient.invalidateQueries({
            queryKey: ["debate-room-draw-vote", sessionIdNum],
          });
          ws.close();
          return;
        }
        if (msg.type === "roomEvent") {
          const ack = buildDebateRoomAckMessage(msg.eventSeq);
          if (msg.eventSeq > 0 && msg.eventSeq <= lastAckSeqRef.current) {
            if (ack) {
              ws.send(ack);
            }
            return;
          }
          if (msg.eventSeq > lastAckSeqRef.current + 1) {
            setPageHint("Realtime gap detected, recovering snapshot...");
            void queryClient.invalidateQueries({
              queryKey: ["debate-room-messages", sessionIdNum],
            });
            void queryClient.invalidateQueries({
              queryKey: ["debate-room-pins", sessionIdNum],
            });
            void queryClient.invalidateQueries({
              queryKey: ["debate-room-judge-report", sessionIdNum],
            });
            void queryClient.invalidateQueries({
              queryKey: ["debate-room-judge-public-verification", sessionIdNum],
            });
            void queryClient.invalidateQueries({
              queryKey: ["debate-room-judge-challenge", sessionIdNum],
            });
            void queryClient.invalidateQueries({
              queryKey: ["debate-room-draw-vote", sessionIdNum],
            });
          } else {
            handleRoomPayload(msg.payload);
          }
          lastAckSeqRef.current = Math.max(lastAckSeqRef.current, msg.eventSeq);
          if (ack) {
            ws.send(ack);
          }
        }
      };
      ws.onclose = () => {
        wsRef.current = null;
        if (!closedRef.current) {
          scheduleReconnect();
        } else {
          setWsStatus("disconnected");
        }
      };
      ws.onerror = () => {
        ws.close();
      };
    } catch (error) {
      setPageHint(toDebateDomainError(error));
      scheduleReconnect();
    }
  }, [
    handleRoomPayload,
    notifyTicket,
    queryClient,
    scheduleReconnect,
    sessionIdNum,
  ]);

  useEffect(() => {
    connectWsRef.current = connectWs;
  }, [connectWs]);

  useEffect(() => {
    closedRef.current = false;
    connectWs();
    return () => {
      closedRef.current = true;
      cleanupWs();
      setWsStatus("disconnected");
    };
  }, [cleanupWs, connectWs]);

  const loadOlder = useCallback(async () => {
    if (historyLoading || !hasMoreHistory) {
      return;
    }
    const oldestId = getOldestDebateMessageId(messages);
    if (!oldestId) {
      setHasMoreHistory(false);
      return;
    }
    setHistoryLoading(true);
    try {
      const result = await listDebateMessages(sessionIdNum, {
        lastId: oldestId,
        limit: HISTORY_LIMIT,
      });
      setMessages((current) => mergeDebateMessages(current, result.items));
      setHasMoreHistory(Boolean(result.hasMore));
    } catch (error) {
      setPageHint(toDebateDomainError(error));
    } finally {
      setHistoryLoading(false);
    }
  }, [hasMoreHistory, historyLoading, messages, sessionIdNum]);

  const wsStatusLabel = useMemo(() => {
    switch (wsStatus) {
      case "connected":
        return "Connected";
      case "connecting":
        return "Connecting";
      case "reconnecting":
        return "Reconnecting";
      default:
        return "Disconnected";
    }
  }, [wsStatus]);

  const finalReport = judgeReportQuery.data?.finalReport ?? null;
  const drawVote = drawVoteQuery.data?.vote ?? null;
  const publicVerificationView = useMemo(
    () =>
      resolveDebateJudgePublicVerificationView(
        judgePublicVerificationQuery.data,
      ),
    [judgePublicVerificationQuery.data],
  );
  const judgeChallengeView = useMemo(
    () => resolveDebateJudgeChallengeView(judgeChallengeQuery.data),
    [judgeChallengeQuery.data],
  );
  const assistantCaseId =
    publicVerificationView.caseId ?? judgeChallengeView.caseId ?? null;
  const normalizedPinSeconds = Math.max(
    1,
    Math.floor(Number(pinSecondsInput) || 60),
  );

  if (!Number.isFinite(sessionIdNum) || sessionIdNum <= 0) {
    return (
      <section className="echo-room-page">
        <SectionTitle>Debate Room</SectionTitle>
        <p className="echo-error">Invalid session id.</p>
      </section>
    );
  }

  return (
    <section className="echo-room-page">
      <header className="echo-room-header">
        <div>
          <SectionTitle>Debate Room #{sessionIdNum}</SectionTitle>
          <p>
            Phase 4 baseline: history paging + realtime stream + send message +
            pinned section.
          </p>
        </div>
        <div className="echo-room-top-actions">
          <InlineHint>Realtime: {wsStatusLabel}</InlineHint>
          <Button onClick={() => navigate("/debate")} type="button">
            Back To Lobby
          </Button>
        </div>
      </header>

      <section className="echo-lobby-summary">
        <article>
          <strong>{messages.length}</strong>
          <span>Messages</span>
        </article>
        <article>
          <strong>{pinsQuery.data?.items.length ?? 0}</strong>
          <span>Pinned</span>
        </article>
        <article>
          <strong>{walletQuery.data?.balance ?? 0}</strong>
          <span>Wallet Coins</span>
        </article>
        <article>
          <strong>
            {(judgeReportQuery.data?.status || "unknown").toUpperCase()}
          </strong>
          <span>Judge Status</span>
        </article>
      </section>

      <DebateNpcPanel state={npcState} />

      <section className="echo-lobby-panel">
        <h3>Pinned Messages</h3>
        {pinsQuery.isLoading ? <InlineHint>Loading pins...</InlineHint> : null}
        {pinsQuery.isError ? (
          <p className="echo-error">{toDebateDomainError(pinsQuery.error)}</p>
        ) : null}
        <div className="echo-room-pins">
          {(pinsQuery.data?.items || []).map((pin) => (
            <article className="echo-topic-item" key={pin.id}>
              <h4>
                {pin.side} | {pin.costCoins} coins | {pin.pinSeconds}s
              </h4>
              <p>{pin.content}</p>
              <InlineHint>Expires: {formatUtc(pin.expiresAt)}</InlineHint>
            </article>
          ))}
          {!pinsQuery.isLoading && (pinsQuery.data?.items.length || 0) === 0 ? (
            <InlineHint>No active pinned messages.</InlineHint>
          ) : null}
        </div>
      </section>

      <section className="echo-lobby-panel">
        <h3>Judge & Draw</h3>
        <div className="echo-lobby-actions">
          <Button
            disabled={requestJudgeMutation.isPending}
            onClick={() => requestJudgeMutation.mutate()}
            type="button"
          >
            {requestJudgeMutation.isPending
              ? "Requesting..."
              : "Request AI Judge"}
          </Button>
          <Button
            disabled={drawVoteMutation.isPending || drawVote?.status !== "open"}
            onClick={() => drawVoteMutation.mutate(true)}
            type="button"
          >
            {drawVoteMutation.isPending ? "Submitting..." : "Vote Draw"}
          </Button>
          <Button
            disabled={drawVoteMutation.isPending || drawVote?.status !== "open"}
            onClick={() => drawVoteMutation.mutate(false)}
            type="button"
          >
            {drawVoteMutation.isPending ? "Submitting..." : "Keep Winner"}
          </Button>
          {drawVote?.rematchSessionId ? (
            <Button
              onClick={() =>
                navigate(`/debate/sessions/${drawVote.rematchSessionId}`)
              }
              type="button"
            >
              Go To Rematch #{drawVote.rematchSessionId}
            </Button>
          ) : null}
        </div>
        {judgeReportQuery.isLoading ? (
          <InlineHint>Loading judge report...</InlineHint>
        ) : null}
        {drawVoteQuery.isLoading ? (
          <InlineHint>Loading draw vote...</InlineHint>
        ) : null}
        {judgePublicVerificationQuery.isLoading ? (
          <InlineHint>Loading public verification...</InlineHint>
        ) : null}
        {judgeChallengeQuery.isLoading ? (
          <InlineHint>Loading challenge status...</InlineHint>
        ) : null}
        {judgeReportQuery.isError ? (
          <p className="echo-error">
            {toDebateDomainError(judgeReportQuery.error)}
          </p>
        ) : null}
        {judgePublicVerificationQuery.isError ? (
          <p className="echo-error">
            {toDebateDomainError(judgePublicVerificationQuery.error)}
          </p>
        ) : null}
        {judgeChallengeQuery.isError ? (
          <p className="echo-error">
            {toDebateDomainError(judgeChallengeQuery.error)}
          </p>
        ) : null}
        {drawVoteQuery.isError ? (
          <p className="echo-error">
            {toDebateDomainError(drawVoteQuery.error)}
          </p>
        ) : null}
        <div className="echo-room-judge-grid">
          <article className="echo-topic-item">
            <h4>Final Report</h4>
            <InlineHint>
              Status: {judgeReportQuery.data?.status || "unknown"}
            </InlineHint>
            {finalReport ? (
              <>
                <p>
                  Winner:{" "}
                  <strong>
                    {String(finalReport.winner || "unknown").toUpperCase()}
                  </strong>
                </p>
                <InlineHint>
                  Score: PRO {finalReport.proScore} vs CON{" "}
                  {finalReport.conScore}
                </InlineHint>
                <InlineHint>
                  Needs Draw Vote: {finalReport.needsDrawVote ? "yes" : "no"} |
                  Degrade: {String(finalReport.degradationLevel ?? "-")}
                </InlineHint>
                <p>{finalReport.finalRationale || "No rationale yet."}</p>
              </>
            ) : (
              <InlineHint>No final report yet.</InlineHint>
            )}
          </article>

          <article className="echo-topic-item">
            <h4>Public Verification</h4>
            <InlineHint>Status: {publicVerificationView.label}</InlineHint>
            <InlineHint>Reason: {publicVerificationView.reasonCode}</InlineHint>
            {publicVerificationView.caseId ? (
              <InlineHint>
                Case: #{publicVerificationView.caseId} | Type:{" "}
                {publicVerificationView.dispatchType}
              </InlineHint>
            ) : null}
            {publicVerificationView.verificationVersion ? (
              <InlineHint>
                Version: {publicVerificationView.verificationVersion}
              </InlineHint>
            ) : null}
            {publicVerificationView.hashSummary ? (
              <InlineHint>
                Hash: {formatPublicHash(publicVerificationView.hashSummary)}
              </InlineHint>
            ) : null}
            {publicVerificationView.blockers.length > 0 ? (
              <InlineHint>
                Blockers: {publicVerificationView.blockers.join(", ")}
              </InlineHint>
            ) : null}
          </article>

          <article className="echo-topic-item">
            <h4>Challenge Review</h4>
            <InlineHint>Status: {judgeChallengeView.label}</InlineHint>
            {judgeChallengeView.caseId ? (
              <InlineHint>
                Case: #{judgeChallengeView.caseId} | Type:{" "}
                {judgeChallengeView.dispatchType}
              </InlineHint>
            ) : null}
            <InlineHint>
              Review: {judgeChallengeView.reviewState} | Challenges:{" "}
              {judgeChallengeView.totalChallenges}
            </InlineHint>
            <InlineHint>
              Verdict Sync: {judgeChallengeView.reviewVisibleStatus} |{" "}
              {judgeChallengeView.reviewSyncState}
            </InlineHint>
            {judgeChallengeView.latestDecision ? (
              <InlineHint>
                Decision: {judgeChallengeView.latestDecision}
              </InlineHint>
            ) : null}
            {judgeChallengeView.blockerLabels.length > 0 ? (
              <InlineHint>
                Blockers: {judgeChallengeView.blockerLabels.join(", ")}
              </InlineHint>
            ) : null}
            {judgeChallengeView.requestable ? (
              <div className="echo-room-card-actions">
                <Button
                  disabled={requestJudgeChallengeMutation.isPending}
                  onClick={() => requestJudgeChallengeMutation.mutate()}
                  type="button"
                >
                  {requestJudgeChallengeMutation.isPending
                    ? "Requesting..."
                    : "Challenge Verdict"}
                </Button>
              </div>
            ) : null}
          </article>

          <article className="echo-topic-item">
            <h4>Draw Vote Status</h4>
            <InlineHint>
              Status: {drawVoteQuery.data?.status || "absent"}
            </InlineHint>
            {drawVote ? (
              <>
                <InlineHint>
                  Participation: {drawVote.participatedVoters}/
                  {drawVote.requiredVoters} (eligible {drawVote.eligibleVoters})
                </InlineHint>
                <InlineHint>
                  Votes: agree {drawVote.agreeVotes} | disagree{" "}
                  {drawVote.disagreeVotes}
                </InlineHint>
                <InlineHint>Resolution: {drawVote.resolution}</InlineHint>
                <InlineHint>
                  My Vote:{" "}
                  {drawVote.myVote == null
                    ? "not submitted"
                    : drawVote.myVote
                      ? "agree draw"
                      : "keep winner"}
                </InlineHint>
                <InlineHint>
                  Voting Ends: {formatUtc(drawVote.votingEndsAt)}
                </InlineHint>
                {drawVote.decidedAt ? (
                  <InlineHint>
                    Decided At: {formatUtc(drawVote.decidedAt)}
                  </InlineHint>
                ) : null}
                {drawVote.rematchSessionId ? (
                  <InlineHint>
                    Rematch Opened: session #{drawVote.rematchSessionId}
                  </InlineHint>
                ) : null}
              </>
            ) : (
              <InlineHint>Draw vote not opened for this session.</InlineHint>
            )}
          </article>
        </div>
      </section>

      <DebateAssistantPanel
        caseId={assistantCaseId}
        onHint={setPageHint}
        sessionId={sessionIdNum}
      />

      <section className="echo-lobby-panel">
        <h3>Message Stream</h3>
        <div className="echo-room-history-actions">
          <Button
            disabled={!hasMoreHistory || historyLoading}
            onClick={() => void loadOlder()}
            type="button"
          >
            {historyLoading
              ? "Loading..."
              : hasMoreHistory
                ? "Load Older Messages"
                : "No Older Messages"}
          </Button>
        </div>
        {messagesQuery.isLoading ? (
          <InlineHint>Loading messages...</InlineHint>
        ) : null}
        {messagesQuery.isError ? (
          <p className="echo-error">
            {toDebateDomainError(messagesQuery.error)}
          </p>
        ) : null}
        <div className="echo-room-message-list">
          {messages.map((message) => (
            <article className="echo-room-message" key={message.id}>
              <header>
                <strong>
                  #{message.id} | {message.side} | user {message.userId}
                </strong>
                <span>{formatUtc(message.createdAt)}</span>
              </header>
              <p>{message.content}</p>
              <div className="echo-lobby-actions">
                <Button
                  disabled={pinMutation.isPending}
                  onClick={() =>
                    pinMutation.mutate({
                      messageId: message.id,
                      pinSeconds: normalizedPinSeconds,
                    })
                  }
                  type="button"
                >
                  {pinMutation.isPending
                    ? "Pinning..."
                    : `Pin ${normalizedPinSeconds}s`}
                </Button>
              </div>
            </article>
          ))}
          {!messagesQuery.isLoading && messages.length === 0 ? (
            <InlineHint>No messages yet.</InlineHint>
          ) : null}
        </div>
      </section>

      <section className="echo-lobby-panel">
        <h3>Send Message</h3>
        <div className="echo-wallet-probe-row">
          <TextField
            aria-label="Pin Seconds"
            inputMode="numeric"
            onChange={(event) => setPinSecondsInput(event.target.value)}
            placeholder="pin seconds"
            value={pinSecondsInput}
          />
          <InlineHint>
            Pin duration applies to the message-level pin action.
          </InlineHint>
        </div>
        <div className="echo-room-composer">
          <textarea
            className="echo-room-input"
            onChange={(event) => setMessageInput(event.target.value)}
            placeholder="Share your argument..."
            rows={3}
            value={messageInput}
          />
          <Button
            disabled={sendMutation.isPending || !messageInput.trim()}
            onClick={() => sendMutation.mutate(messageInput)}
            type="button"
          >
            {sendMutation.isPending ? "Sending..." : "Send"}
          </Button>
        </div>
      </section>

      {pageHint ? <InlineHint>{pageHint}</InlineHint> : null}
    </section>
  );
}
