import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  joinDebateSession,
  listDebateSessions,
  listDebateTopics,
  normalizeDebateStatusFilter,
  toDebateDomainError,
  type DebateSide,
  type DebateStatusFilter
} from "@echoisle/debate-domain";
import { Button, InlineHint, SectionTitle } from "@echoisle/ui";

const STATUS_OPTIONS: Array<{ label: string; value: DebateStatusFilter }> = [
  { label: "All", value: "all" },
  { label: "Open", value: "open" },
  { label: "Running", value: "running" },
  { label: "Judging", value: "judging" },
  { label: "Closed", value: "closed" }
];

function formatUtc(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString();
}

export function DebateLobbyPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<DebateStatusFilter>("all");
  const [joinHint, setJoinHint] = useState<string | null>(null);

  const topicsQuery = useQuery({
    queryKey: ["debate-topics"],
    queryFn: () => listDebateTopics({ activeOnly: true, limit: 8 })
  });

  const sessionsQuery = useQuery({
    queryKey: ["debate-sessions", statusFilter],
    queryFn: () => listDebateSessions({ status: statusFilter, limit: 20 })
  });

  const joinMutation = useMutation({
    mutationFn: async (payload: { sessionId: number; side: DebateSide }) =>
      joinDebateSession(payload.sessionId, payload.side),
    onSuccess: (result) => {
      setJoinHint(
        `Joined session #${result.sessionId} as ${result.side.toUpperCase()} (${result.proCount} vs ${result.conCount})`
      );
      void queryClient.invalidateQueries({ queryKey: ["debate-sessions"] });
      navigate(`/debate/sessions/${result.sessionId}`);
    },
    onError: (error) => {
      setJoinHint(toDebateDomainError(error));
    }
  });

  const sessionCountLabel = useMemo(() => {
    if (!sessionsQuery.data) {
      return "0";
    }
    return `${sessionsQuery.data.items.length}`;
  }, [sessionsQuery.data]);

  return (
    <section className="echo-lobby-page">
      <header className="echo-lobby-header">
        <SectionTitle>Debate Lobby</SectionTitle>
        <p>Phase 4 baseline: real topics/sessions data with direct join actions.</p>
      </header>

      <section className="echo-lobby-summary">
        <article>
          <strong>{topicsQuery.data?.items.length ?? 0}</strong>
          <span>Active Topics</span>
        </article>
        <article>
          <strong>{sessionCountLabel}</strong>
          <span>Sessions</span>
        </article>
        <article>
          <strong>{normalizeDebateStatusFilter(statusFilter).toUpperCase()}</strong>
          <span>Status Filter</span>
        </article>
      </section>

      <section className="echo-lobby-panel">
        <h3>Session Status</h3>
        <div className="echo-type-switch" role="group" aria-label="session status">
          {STATUS_OPTIONS.map((option) => (
            <button
              key={option.value}
              className={statusFilter === option.value ? "is-selected" : ""}
              onClick={() => setStatusFilter(option.value)}
              type="button"
            >
              {option.label}
            </button>
          ))}
        </div>
      </section>

      <section className="echo-lobby-panel">
        <h3>Topics</h3>
        {topicsQuery.isLoading ? <InlineHint>Loading topics...</InlineHint> : null}
        {topicsQuery.isError ? <p className="echo-error">{toDebateDomainError(topicsQuery.error)}</p> : null}
        <div className="echo-topic-grid">
          {(topicsQuery.data?.items || []).map((topic) => (
            <article className="echo-topic-item" key={topic.id}>
              <h4>{topic.title}</h4>
              <p>{topic.description}</p>
              <InlineHint>
                {topic.category} | {topic.stancePro} vs {topic.stanceCon}
              </InlineHint>
            </article>
          ))}
          {!topicsQuery.isLoading && (topicsQuery.data?.items.length || 0) === 0 ? (
            <InlineHint>No topics yet.</InlineHint>
          ) : null}
        </div>
      </section>

      <section className="echo-lobby-panel">
        <h3>Sessions</h3>
        {sessionsQuery.isLoading ? <InlineHint>Loading sessions...</InlineHint> : null}
        {sessionsQuery.isError ? <p className="echo-error">{toDebateDomainError(sessionsQuery.error)}</p> : null}
        <div className="echo-session-grid">
          {(sessionsQuery.data?.items || []).map((session) => (
            <article className="echo-session-item" key={session.id}>
              <header>
                <strong>Session #{session.id}</strong>
                <span className={`echo-session-status is-${session.status.toLowerCase()}`}>{session.status}</span>
              </header>
              <p>
                Topic #{session.topicId} | Hot {session.hotScore} | {session.proCount} vs {session.conCount}
              </p>
              <InlineHint>Start: {formatUtc(session.scheduledStartAt)}</InlineHint>
              <InlineHint>End: {formatUtc(session.endAt)}</InlineHint>
              <div className="echo-lobby-actions">
                <Button
                  disabled={!session.joinable || joinMutation.isPending}
                  onClick={() => joinMutation.mutate({ sessionId: session.id, side: "pro" })}
                  type="button"
                >
                  Join Pro
                </Button>
                <Button
                  disabled={!session.joinable || joinMutation.isPending}
                  onClick={() => joinMutation.mutate({ sessionId: session.id, side: "con" })}
                  type="button"
                >
                  Join Con
                </Button>
                <Button onClick={() => navigate(`/debate/sessions/${session.id}`)} type="button">
                  Enter Room
                </Button>
              </div>
            </article>
          ))}
          {!sessionsQuery.isLoading && (sessionsQuery.data?.items.length || 0) === 0 ? (
            <InlineHint>No sessions matched this filter.</InlineHint>
          ) : null}
        </div>
      </section>

      {joinHint ? <InlineHint>{joinHint}</InlineHint> : null}
    </section>
  );
}
