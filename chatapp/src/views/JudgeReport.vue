<template>
  <div class="flex h-screen echo-shell">
    <Sidebar />
    <div class="echo-main">
      <div class="max-w-5xl mx-auto p-6 lg:p-8 space-y-5 echo-fade-in">
        <div class="echo-panel-strong relative overflow-hidden p-5 lg:p-6">
          <div class="absolute inset-0 bg-gradient-to-br from-indigo-100/70 via-white to-sky-100/70"></div>
          <div class="absolute -left-20 -top-20 w-64 h-64 rounded-full bg-indigo-200/35 blur-3xl"></div>
          <div class="absolute -right-20 -bottom-20 w-64 h-64 rounded-full bg-sky-200/35 blur-3xl"></div>
          <div class="relative flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div class="max-w-3xl">
              <div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">AI Judge Report</div>
              <h1 class="text-2xl font-semibold text-slate-900 mt-1">裁判报告中心</h1>
              <p class="text-sm text-slate-700 mt-2">
                输入辩论 session id，查看 AI 判决、阶段摘要与实时刷新质量指标。
              </p>
              <div class="mt-3 flex flex-wrap gap-2 text-xs">
                <span class="inline-flex items-center rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-slate-700">
                  状态 {{ reportData?.status || 'idle' }}
                </span>
                <span class="inline-flex items-center rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-slate-700">
                  阶段 {{ stageSummaries.length }}
                </span>
                <span class="inline-flex items-center rounded-full border border-slate-200 bg-white/90 px-3 py-1 text-slate-700">
                  刷新事件 {{ realtimeStats.receivedEvents }}
                </span>
              </div>
            </div>
            <div class="w-full lg:w-[280px] echo-panel p-3 bg-white/85">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">判决链路观测面板</div>
              <div class="mt-2 text-xs text-slate-700">
                聚合展示自动刷新成功率、缓存命中、DB 延迟，便于排查判决链路波动。
              </div>
            </div>
          </div>
        </div>

        <div class="echo-panel p-4">
          <div class="text-xs uppercase tracking-[0.18em] text-slate-500 mb-2">查询条件</div>
          <div class="flex gap-3 items-center">
            <input
              v-model="sessionIdInput"
              type="text"
              class="echo-field flex-1"
              placeholder="例如：123"
            />
            <button
              @click="loadReport"
              :disabled="loading"
              class="echo-btn-primary disabled:opacity-50"
            >
              {{ loading ? '查询中...' : '查询' }}
            </button>
          </div>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 text-sm border border-red-200 rounded p-3">
          {{ errorText }}
        </div>

        <div class="echo-panel p-4">
          <div class="text-xs uppercase tracking-[0.18em] text-gray-500 mb-2">Realtime Refresh</div>
          <div class="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
            <div class="rounded-xl border border-slate-200 bg-white/80 p-3">
              <div class="text-xs uppercase text-gray-500">Events</div>
              <div class="font-semibold text-gray-900">{{ realtimeStats.receivedEvents }}</div>
            </div>
            <div class="rounded-xl border border-emerald-200 bg-emerald-50/70 p-3">
              <div class="text-xs uppercase text-gray-500">Success</div>
              <div class="font-semibold text-green-700">{{ realtimeStats.refreshSuccess }}</div>
            </div>
            <div class="rounded-xl border border-red-200 bg-red-50/70 p-3">
              <div class="text-xs uppercase text-gray-500">Failure</div>
              <div class="font-semibold text-red-700">{{ realtimeStats.refreshFailure }}</div>
            </div>
            <div class="rounded-xl border border-amber-200 bg-amber-50/70 p-3">
              <div class="text-xs uppercase text-gray-500">Retry</div>
              <div class="font-semibold text-amber-700">{{ realtimeStats.retryTriggered }}</div>
            </div>
            <div class="rounded-xl border border-indigo-200 bg-indigo-50/70 p-3">
              <div class="text-xs uppercase text-gray-500">Coalesced</div>
              <div class="font-semibold text-indigo-700">{{ realtimeStats.coalescedEvents }}</div>
            </div>
          </div>
          <div class="text-xs text-gray-500 mt-2">
            lastEvent: {{ realtimeStats.lastEventType || '-' }} |
            lastRefreshAt: {{ formatDateTime(realtimeStats.lastRefreshAt) }} |
            lastError: {{ realtimeStats.lastError || '-' }}
          </div>
        </div>

        <div class="echo-panel p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-xs uppercase text-gray-500">Refresh Summary (Analytics)</div>
              <div class="text-xs text-gray-500">
                window: {{ summaryWindowHours }}h | limit: {{ summaryLimit }} |
                updatedAt: {{ formatDateTime(summaryUpdatedAt) }}
              </div>
            </div>
            <button
              @click="refreshSummary"
              :disabled="summaryLoading || loading"
              class="echo-btn-secondary text-xs px-3 py-1 disabled:opacity-50"
            >
              {{ summaryLoading ? '刷新中...' : '刷新汇总' }}
            </button>
          </div>

          <div v-if="summaryErrorText" class="bg-red-50 text-red-700 text-xs border border-red-200 rounded p-2">
            {{ summaryErrorText }}
          </div>

          <div v-if="summaryRows.length === 0" class="text-sm text-gray-500">
            当前没有刷新汇总数据。
          </div>

          <div v-else class="overflow-x-auto">
            <table class="min-w-full text-xs border rounded">
              <thead class="bg-gray-50 text-gray-600">
                <tr>
                  <th class="text-left p-2 border-b">Session</th>
                  <th class="text-left p-2 border-b">Source</th>
                  <th class="text-right p-2 border-b">Success Rate</th>
                  <th class="text-right p-2 border-b">Runs</th>
                  <th class="text-right p-2 border-b">Avg Retry</th>
                  <th class="text-right p-2 border-b">Avg Coalesced</th>
                  <th class="text-right p-2 border-b">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in summaryRows" :key="summaryRowKey(row)">
                  <td class="p-2 border-b text-gray-900">{{ row.debateSessionId || '-' }}</td>
                  <td class="p-2 border-b text-gray-700">{{ row.sourceEventType || '-' }}</td>
                  <td class="p-2 border-b text-right text-gray-900">{{ formatPercent(row.successRate) }}</td>
                  <td class="p-2 border-b text-right text-gray-900">{{ row.totalRuns || 0 }}</td>
                  <td class="p-2 border-b text-right text-gray-900">{{ row.avgRetryCount ?? 0 }}</td>
                  <td class="p-2 border-b text-right text-gray-900">{{ row.avgCoalescedEvents ?? 0 }}</td>
                  <td class="p-2 border-b text-right text-gray-700">{{ formatDateTime(row.lastSeenAtMs) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="echo-panel p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div>
              <div class="text-xs uppercase text-gray-500">Summary Metrics (Debug)</div>
              <div class="text-xs text-gray-500">
                updatedAt: {{ formatDateTime(summaryMetricsUpdatedAt) }}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button
                @click="toggleSummaryMetricsPanel"
                class="px-3 py-1 rounded border text-xs bg-white hover:bg-gray-100"
              >
                {{ summaryMetricsPanelOpen ? '收起' : '展开' }}
              </button>
              <button
                @click="refreshSummaryMetrics"
                :disabled="summaryMetricsLoading || loading"
                class="echo-btn-secondary text-xs px-3 py-1 disabled:opacity-50"
              >
                {{ summaryMetricsLoading ? '刷新中...' : '刷新指标' }}
              </button>
            </div>
          </div>

          <div v-if="summaryMetricsPanelOpen">
            <div
              v-if="summaryMetricsErrorText"
              class="bg-red-50 text-red-700 text-xs border border-red-200 rounded p-2 mb-2"
            >
              {{ summaryMetricsErrorText }}
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <div class="text-xs uppercase text-gray-500">Requests</div>
                <div class="font-semibold text-gray-900">{{ summaryMetrics.requestTotal }}</div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Cache Hit</div>
                <div class="font-semibold text-green-700">{{ summaryMetrics.cacheHitTotal }}</div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Cache Miss</div>
                <div class="font-semibold text-amber-700">{{ summaryMetrics.cacheMissTotal }}</div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Hit Rate</div>
                <div class="font-semibold text-indigo-700">
                  {{ formatPercent(summaryMetrics.cacheHitRate) }}
                </div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Miss Rate</div>
                <div class="font-semibold text-orange-700">
                  {{ formatPercent(summaryCacheMissRate) }}
                </div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">DB Queries</div>
                <div class="font-semibold text-gray-900">{{ summaryMetrics.dbQueryTotal }}</div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">DB Errors</div>
                <div class="font-semibold text-red-700">{{ summaryMetrics.dbErrorTotal }}</div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Avg DB Latency</div>
                <div class="font-semibold text-gray-900">
                  {{ formatDecimal(summaryMetrics.avgDbLatencyMs) }} ms
                </div>
              </div>
            </div>
            <div class="text-xs text-gray-500 mt-2">
              lastDbLatency: {{ formatDecimal(summaryMetrics.lastDbLatencyMs) }} ms
            </div>
          </div>
        </div>

        <div v-if="reportData" class="space-y-4">
          <div class="echo-panel p-4">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-xs uppercase text-gray-500">Session</div>
                <div class="font-semibold text-gray-900">{{ reportData.sessionId }}</div>
              </div>
              <div class="text-right">
                <div class="text-xs uppercase text-gray-500">Status</div>
                <div class="font-semibold" :class="statusClass(reportData.status)">
                  {{ reportData.status }}
                </div>
              </div>
            </div>
          </div>

          <div v-if="finalDispatchDiagnostics" class="echo-panel p-4 space-y-3">
            <div class="text-xs uppercase text-gray-500">Final Dispatch Diagnostics</div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <div class="text-xs uppercase text-gray-500">Final Job</div>
                <div class="font-semibold text-gray-900">{{ finalDispatchDiagnostics.finalJobId }}</div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Dispatch Status</div>
                <div class="font-semibold text-gray-900">{{ finalDispatchDiagnostics.status }}</div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Failure Type</div>
                <div class="font-semibold text-gray-900">
                  {{ finalDispatchDiagnostics.contractFailureType || '-' }}
                </div>
              </div>
              <div>
                <div class="text-xs uppercase text-gray-500">Action</div>
                <div class="font-semibold text-gray-900">
                  {{ finalDispatchActionText(finalDispatchDiagnostics.contractFailureAction) }}
                </div>
              </div>
            </div>
            <div
              v-if="finalDispatchDiagnostics.contractFailureHint"
              class="text-sm border rounded p-3 bg-amber-50 border-amber-200 text-amber-800"
            >
              {{ finalDispatchDiagnostics.contractFailureHint }}
            </div>
            <div
              v-if="finalDispatchDiagnostics.errorMessage"
              class="text-xs text-gray-600 bg-gray-50 border rounded p-2 break-all"
            >
              error: {{ finalDispatchDiagnostics.errorMessage }}
            </div>

            <div v-if="finalDispatchFailureStats" class="space-y-2">
              <div class="text-xs uppercase text-gray-500">Failure Stats (Session)</div>
              <div class="text-xs text-gray-600">
                totalFailedJobs: {{ finalDispatchFailureStats.totalFailedJobs }} |
                unknownFailedJobs: {{ finalDispatchFailureStats.unknownFailedJobs }}
              </div>
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="item in finalDispatchFailureStats.byType || []"
                  :key="item.failureType"
                  class="text-xs px-2 py-1 rounded border bg-gray-50 text-gray-700"
                >
                  {{ item.failureType }}: {{ item.count }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="!report" class="echo-panel p-4 text-sm text-gray-600">
            当前还没有可展示的判决报告（可能仍在处理中）。
          </div>

          <template v-else>
            <div class="echo-panel p-4">
              <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div class="text-xs uppercase text-gray-500">Winner</div>
                  <div class="text-lg font-bold text-gray-900">{{ report.winner }}</div>
                </div>
                <div>
                  <div class="text-xs uppercase text-gray-500">Pro Score</div>
                  <div class="text-lg font-semibold text-blue-700">{{ report.proScore }}</div>
                </div>
                <div>
                  <div class="text-xs uppercase text-gray-500">Con Score</div>
                  <div class="text-lg font-semibold text-orange-700">{{ report.conScore }}</div>
                </div>
                <div>
                  <div class="text-xs uppercase text-gray-500">Style</div>
                  <div class="text-sm font-semibold text-gray-800">{{ report.styleMode }}</div>
                </div>
              </div>
            </div>

            <div v-if="showDrawVoteCard" class="echo-panel p-4 space-y-3">
              <div class="flex items-center justify-between">
                <div class="text-xs uppercase text-gray-500">Draw Vote</div>
                <button
                  @click="refreshDrawVote(reportData.sessionId)"
                  :disabled="drawVoteLoading || voteSubmitting"
                  class="echo-btn-secondary text-xs px-3 py-1 disabled:opacity-50"
                >
                  {{ drawVoteLoading ? '刷新中...' : '刷新投票状态' }}
                </button>
              </div>

              <div v-if="!drawVote" class="text-sm text-gray-500">
                当前没有可用的平局投票信息。
              </div>

              <template v-else>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div>
                    <div class="text-xs uppercase text-gray-500">Status</div>
                    <div class="font-semibold text-gray-900">{{ drawVote.status }}</div>
                  </div>
                  <div>
                    <div class="text-xs uppercase text-gray-500">参加/门槛</div>
                    <div class="font-semibold text-gray-900">
                      {{ drawVote.participatedVoters }} / {{ drawVote.requiredVoters }}
                    </div>
                  </div>
                  <div>
                    <div class="text-xs uppercase text-gray-500">同意/不同意</div>
                    <div class="font-semibold text-gray-900">
                      {{ drawVote.agreeVotes }} / {{ drawVote.disagreeVotes }}
                    </div>
                  </div>
                  <div>
                    <div class="text-xs uppercase text-gray-500">我的投票</div>
                    <div class="font-semibold text-gray-900">
                      {{ drawVoteChoiceText(drawVote.myVote) }}
                    </div>
                  </div>
                </div>

                <div class="text-xs text-gray-500">
                  投票截止时间：{{ formatDateTime(drawVote.votingEndsAt) }}
                </div>

                <div class="text-xs text-gray-500">
                  判定来源：{{ drawVoteDecisionSourceText(drawVote.decisionSource) }}
                </div>

                <div v-if="canSubmitVote" class="flex flex-wrap gap-2">
                  <button
                    @click="submitVote(true)"
                    :disabled="voteSubmitting"
                    class="px-3 py-2 rounded bg-green-600 text-white text-sm disabled:opacity-50"
                  >
                    {{ voteSubmitting ? '提交中...' : '同意平局（不二番战）' }}
                  </button>
                  <button
                    @click="submitVote(false)"
                    :disabled="voteSubmitting"
                    class="px-3 py-2 rounded bg-orange-600 text-white text-sm disabled:opacity-50"
                  >
                    {{ voteSubmitting ? '提交中...' : '不同意平局（开启二番战）' }}
                  </button>
                </div>

                <div v-else class="text-sm text-gray-700">
                  {{ drawVoteResolutionText(drawVote.resolution) }}
                  <span v-if="drawVote.rematchSessionId">
                    ，二番战 session: {{ drawVote.rematchSessionId }}
                  </span>
                </div>
              </template>
            </div>

            <div class="echo-panel p-4">
              <div class="text-xs uppercase text-gray-500 mb-2">Rationale</div>
              <p class="text-sm text-gray-800 whitespace-pre-wrap">{{ report.rationale }}</p>
            </div>

            <div class="echo-panel p-4">
              <div class="text-xs uppercase text-gray-500 mb-2">RAG</div>
              <div v-if="report.rag" class="text-sm text-gray-700 space-y-1">
                <div>snippetCount: {{ report.rag.snippetCount ?? 0 }}</div>
                <div>sources: {{ (report.rag.sources || []).length }}</div>
                <div>usedByModel: {{ report.rag.usedByModel ? 'true' : 'false' }}</div>
              </div>
              <div v-else class="text-sm text-gray-500">无 RAG 元信息</div>
            </div>

            <div class="echo-panel p-4">
              <div class="flex items-center justify-between mb-3">
                <div class="text-xs uppercase text-gray-500">Stage Summaries</div>
                <div v-if="stageMeta" class="text-xs text-gray-500">
                  returned {{ stageMeta.returnedCount }} / total {{ stageMeta.totalCount }}
                  (offset {{ stageMeta.stageOffset }})
                </div>
              </div>

              <div v-if="stageSummaries.length === 0" class="text-sm text-gray-500">
                当前报告没有阶段摘要。
              </div>

              <div v-else class="space-y-3">
                <div
                  v-for="stage in stageSummaries"
                  :key="stage.stageNo"
                  class="border rounded p-3 bg-gray-50"
                >
                  <div class="flex items-center justify-between mb-2">
                    <div class="font-semibold text-sm text-gray-900">
                      Stage {{ stage.stageNo }}
                    </div>
                    <div class="text-xs text-gray-600">
                      Pro {{ stage.proScore }} / Con {{ stage.conScore }}
                    </div>
                  </div>
                  <div class="text-xs text-gray-500 mb-2">
                    message range: {{ stage.fromMessageId ?? '-' }} ~ {{ stage.toMessageId ?? '-' }}
                  </div>
                  <pre class="text-xs bg-white border rounded p-2 overflow-x-auto">{{ jsonText(stage.summary) }}</pre>
                </div>
              </div>

              <div v-if="canLoadMore" class="mt-4">
                <button
                  @click="loadMoreStages"
                  :disabled="loadingMore"
                  class="px-4 py-2 rounded border text-sm bg-white hover:bg-gray-100 disabled:opacity-50"
                >
                  {{ loadingMore ? '加载中...' : '继续加载阶段摘要' }}
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import Sidebar from '../components/Sidebar.vue';
import {
  drawVoteChoiceText as drawVoteChoiceTextLabel,
  drawVoteDecisionSourceText as drawVoteDecisionSourceTextLabel,
  drawVoteResolutionText as drawVoteResolutionLabel,
  isDrawVoteOpen,
  mergeJudgeReportWindow,
  normalizeSessionId,
} from '../judge-report-utils';
import {
  shouldRetryAutoRefresh,
} from '../realtime-refresh-utils';
import { runAutoRefreshWithRetry } from '../realtime-refresh-runner';

const AUTO_REFRESH_THROTTLE_MS = 1200;
const AUTO_REFRESH_BUSY_RECHECK_MS = 300;

export default {
  components: {
    Sidebar,
  },
  data() {
    return {
      sessionIdInput: '',
      reportData: null,
      drawVoteData: null,
      loading: false,
      loadingMore: false,
      drawVoteLoading: false,
      voteSubmitting: false,
      autoRefreshBusy: false,
      autoRefreshTimer: null,
      pendingAutoRefresh: null,
      lastAutoRefreshAt: 0,
      errorText: '',
      windowSize: 3,
      realtimeStats: {
        receivedEvents: 0,
        refreshSuccess: 0,
        refreshFailure: 0,
        retryTriggered: 0,
        coalescedEvents: 0,
        lastEventType: '',
        lastRefreshAt: null,
        lastError: '',
      },
      summaryWindowHours: 24,
      summaryLimit: 20,
      summaryRows: [],
      summaryLoading: false,
      summaryUpdatedAt: null,
      summaryErrorText: '',
      summaryMetricsPanelOpen: false,
      summaryMetricsLoading: false,
      summaryMetricsUpdatedAt: null,
      summaryMetricsErrorText: '',
      summaryMetrics: {
        requestTotal: 0,
        cacheHitTotal: 0,
        cacheMissTotal: 0,
        cacheHitRate: 0,
        dbQueryTotal: 0,
        dbErrorTotal: 0,
        avgDbLatencyMs: 0,
        lastDbLatencyMs: 0,
      },
    };
  },
  computed: {
    report() {
      return this.reportData?.report || null;
    },
    finalDispatchDiagnostics() {
      return this.reportData?.finalDispatchDiagnostics || null;
    },
    finalDispatchFailureStats() {
      return this.reportData?.finalDispatchFailureStats || null;
    },
    stageSummaries() {
      return this.report?.stageSummaries || [];
    },
    stageMeta() {
      return this.report?.stageSummariesMeta || null;
    },
    drawVote() {
      return this.drawVoteData?.vote || null;
    },
    canLoadMore() {
      return !!(this.stageMeta && this.stageMeta.hasMore && !this.loadingMore && !this.loading);
    },
    showDrawVoteCard() {
      return !!(this.report?.needsDrawVote || this.drawVote);
    },
    canSubmitVote() {
      return !!(this.drawVote && isDrawVoteOpen(this.drawVote) && !this.voteSubmitting);
    },
    latestJudgeReportEvent() {
      return this.$store.state.latestJudgeReportEvent;
    },
    latestDrawVoteResolvedEvent() {
      return this.$store.state.latestDrawVoteResolvedEvent;
    },
    summaryCacheMissRate() {
      const missRate = 100 - Number(this.summaryMetrics.cacheHitRate || 0);
      return Math.max(0, missRate);
    },
  },
  watch: {
    latestJudgeReportEvent(event) {
      this.handleJudgeReportReadyEvent(event);
    },
    latestDrawVoteResolvedEvent(event) {
      this.handleDrawVoteResolvedEvent(event);
    },
  },
  async mounted() {
    const sessionId = normalizeSessionId(this.$route?.query?.sessionId);
    if (!sessionId) {
      return;
    }
    this.sessionIdInput = String(sessionId);
    await this.loadReport();
  },
  beforeUnmount() {
    this.clearAutoRefreshTimer();
  },
  methods: {
    statusClass(status) {
      if (status === 'ready') return 'text-green-700';
      if (status === 'pending') return 'text-amber-700';
      if (status === 'failed') return 'text-red-700';
      return 'text-gray-700';
    },
    jsonText(value) {
      return JSON.stringify(value || {}, null, 2);
    },
    formatDateTime(value) {
      if (!value) return '-';
      const d = new Date(value);
      if (Number.isNaN(d.getTime())) return String(value);
      return d.toLocaleString();
    },
    formatPercent(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return '-';
      return `${n.toFixed(2)}%`;
    },
    formatDecimal(value) {
      const n = Number(value);
      if (!Number.isFinite(n)) return '-';
      return n.toFixed(2);
    },
    summaryRowKey(row) {
      return `${row.debateSessionId || ''}:${row.sourceEventType || ''}`;
    },
    toggleSummaryMetricsPanel() {
      this.summaryMetricsPanelOpen = !this.summaryMetricsPanelOpen;
    },
    drawVoteChoiceText(myVote) {
      return drawVoteChoiceTextLabel(myVote);
    },
    drawVoteDecisionSourceText(decisionSource) {
      return drawVoteDecisionSourceTextLabel(decisionSource);
    },
    drawVoteResolutionText(resolution) {
      return drawVoteResolutionLabel(resolution);
    },
    finalDispatchActionText(action) {
      if (!action) return '-';
      if (action === 'check_phase_artifacts_then_retry') return '检查阶段产物后重试';
      if (action === 'check_ai_judge_acceptance_then_retry') return '检查 AI 接口响应后重试';
      if (action === 'check_dispatch_contract_alignment') return '检查 dispatch 契约一致性';
      if (action === 'inspect_error_then_retry_or_escalate') return '先排障再重试，必要时升级处理';
      if (action === 'inspect_error_then_retry') return '查看错误后重试';
      return action;
    },
    errorMessage(err) {
      return err?.response?.data?.error || err?.message || '请求失败';
    },
    patchRealtimeStats(delta) {
      this.realtimeStats = {
        ...this.realtimeStats,
        ...delta,
      };
    },
    clearAutoRefreshTimer() {
      if (this.autoRefreshTimer) {
        clearTimeout(this.autoRefreshTimer);
        this.autoRefreshTimer = null;
      }
    },
    scheduleAutoRefreshFlush(delayMs) {
      this.clearAutoRefreshTimer();
      this.autoRefreshTimer = setTimeout(() => {
        this.autoRefreshTimer = null;
        this.maybeFlushPendingAutoRefresh();
      }, Math.max(0, Number(delayMs) || 0));
    },
    canRunAutoRefreshNow() {
      return !(
        this.autoRefreshBusy ||
        this.loading ||
        this.loadingMore ||
        this.voteSubmitting
      );
    },
    enqueueRealtimeRefresh(sessionId, sourceEventType) {
      if (!sessionId) return;
      if (this.pendingAutoRefresh) {
        this.patchRealtimeStats({
          coalescedEvents: this.realtimeStats.coalescedEvents + 1,
        });
        this.pendingAutoRefresh = {
          ...this.pendingAutoRefresh,
          sourceEventType,
          coalescedCount: Number(this.pendingAutoRefresh.coalescedCount || 0) + 1,
        };
      } else {
        this.pendingAutoRefresh = {
          sessionId,
          sourceEventType,
          coalescedCount: 0,
        };
      }
      this.maybeFlushPendingAutoRefresh();
    },
    maybeFlushPendingAutoRefresh() {
      if (!this.pendingAutoRefresh) {
        return;
      }
      if (!this.canRunAutoRefreshNow()) {
        this.scheduleAutoRefreshFlush(AUTO_REFRESH_BUSY_RECHECK_MS);
        return;
      }
      const now = Date.now();
      const waitMs = Math.max(0, AUTO_REFRESH_THROTTLE_MS - (now - this.lastAutoRefreshAt));
      if (waitMs > 0) {
        this.scheduleAutoRefreshFlush(waitMs);
        return;
      }
      this.flushPendingAutoRefresh();
    },
    currentSessionId() {
      if (this.reportData?.sessionId) {
        return Number(this.reportData.sessionId);
      }
      return normalizeSessionId(this.sessionIdInput);
    },
    shouldHandleSessionEvent(event) {
      const eventSessionId = Number(event?.sessionId || 0);
      const currentSessionId = Number(this.currentSessionId() || 0);
      return eventSessionId > 0 && currentSessionId > 0 && eventSessionId === currentSessionId;
    },
    async refreshDrawVote(sessionId, { silent = false } = {}) {
      if (!silent) {
        this.drawVoteLoading = true;
      }
      try {
        const payload = await this.$store.dispatch('fetchDrawVoteStatus', { sessionId });
        this.drawVoteData = payload;
      } finally {
        if (!silent) {
          this.drawVoteLoading = false;
        }
      }
    },
    async fetchReportForSession(sessionId, { silent = false, throwOnError = false } = {}) {
      if (!silent) {
        this.loading = true;
        this.errorText = '';
        this.drawVoteData = null;
      }
      try {
        const maxStageCount = silent
          ? Math.max(this.stageSummaries.length || 0, this.windowSize)
          : this.windowSize;
        const payload = await this.$store.dispatch('fetchJudgeReport', {
          sessionId,
          maxStageCount,
          stageOffset: 0,
        });
        this.reportData = payload;
        if (payload?.report) {
          await this.refreshDrawVote(sessionId, { silent });
        }
      } catch (err) {
        if (silent) {
          if (throwOnError) {
            throw err;
          }
          console.warn('silent judge report refresh failed:', err);
        } else {
          this.errorText = this.errorMessage(err);
        }
      } finally {
        if (!silent) {
          this.loading = false;
        }
      }
    },
    async loadRefreshSummary(sessionId, { silent = false } = {}) {
      if (!sessionId) return;
      if (!silent) {
        this.summaryLoading = true;
      }
      if (!silent) {
        this.summaryErrorText = '';
      }
      try {
        const payload = await this.$store.dispatch('fetchJudgeRefreshSummary', {
          debateSessionId: sessionId,
          hours: this.summaryWindowHours,
          limit: this.summaryLimit,
        });
        this.summaryWindowHours = Number(payload?.windowHours || this.summaryWindowHours);
        this.summaryLimit = Number(payload?.limit || this.summaryLimit);
        this.summaryRows = Array.isArray(payload?.rows) ? payload.rows : [];
        this.summaryUpdatedAt = Date.now();
        this.loadRefreshSummaryMetrics({ silent: true, suppressOnError: true }).catch(() => {});
      } catch (err) {
        if (!silent) {
          this.summaryErrorText = this.errorMessage(err);
        }
      } finally {
        if (!silent) {
          this.summaryLoading = false;
        }
      }
    },
    async loadRefreshSummaryMetrics({ silent = false, suppressOnError = false } = {}) {
      if (!silent) {
        this.summaryMetricsLoading = true;
      }
      if (!silent) {
        this.summaryMetricsErrorText = '';
      }
      try {
        const payload = await this.$store.dispatch('fetchJudgeRefreshSummaryMetrics');
        this.summaryMetrics = {
          ...this.summaryMetrics,
          ...(payload || {}),
        };
        this.summaryMetricsUpdatedAt = Date.now();
      } catch (err) {
        if (!silent && !suppressOnError) {
          this.summaryMetricsErrorText = this.errorMessage(err);
        }
      } finally {
        if (!silent) {
          this.summaryMetricsLoading = false;
        }
      }
    },
    async refreshSummaryMetrics() {
      await this.loadRefreshSummaryMetrics();
    },
    async flushPendingAutoRefresh() {
      if (!this.pendingAutoRefresh || !this.canRunAutoRefreshNow()) {
        this.maybeFlushPendingAutoRefresh();
        return;
      }
      const pending = this.pendingAutoRefresh;
      this.pendingAutoRefresh = null;
      let retryCountInRun = 0;
      let lastRunErrorMessage = '';
      this.autoRefreshBusy = true;
      try {
        const result = await runAutoRefreshWithRetry({
          fetchOnce: () => this.fetchReportForSession(pending.sessionId, { silent: true, throwOnError: true }),
          sourceEventType: pending.sourceEventType,
          shouldRetry: shouldRetryAutoRefresh,
          onRetry: () => {
            retryCountInRun += 1;
            this.patchRealtimeStats({
              retryTriggered: this.realtimeStats.retryTriggered + 1,
            });
          },
          onSuccess: (v) => {
            this.patchRealtimeStats({
              refreshSuccess: this.realtimeStats.refreshSuccess + 1,
              lastRefreshAt: v.at,
              lastError: '',
              lastEventType: pending.sourceEventType,
            });
          },
          onFailure: (v) => {
            lastRunErrorMessage = this.errorMessage(v.error);
            this.patchRealtimeStats({
              refreshFailure: this.realtimeStats.refreshFailure + 1,
              lastRefreshAt: v.at,
              lastEventType: pending.sourceEventType,
              lastError: lastRunErrorMessage,
            });
          },
        });
        this.lastAutoRefreshAt = result.at || Date.now();
        this.emitRealtimeTelemetry({
          pending,
          result,
          retryCountInRun,
          errorMessage: lastRunErrorMessage,
        });
        this.loadRefreshSummary(pending.sessionId, { silent: true }).catch((err) => {
          console.warn('silent refresh summary failed:', err);
        });
      } finally {
        this.autoRefreshBusy = false;
        if (this.pendingAutoRefresh) {
          this.maybeFlushPendingAutoRefresh();
        }
      }
    },
    emitRealtimeTelemetry({ pending, result, retryCountInRun, errorMessage }) {
      this.$store.dispatch('judgeRealtimeRefresh', {
        debateSessionId: String(pending.sessionId),
        sourceEventType: pending.sourceEventType,
        result: result.ok ? 'success' : 'failure',
        attempts: result.attempt,
        retryCount: retryCountInRun,
        coalescedEvents: Number(pending.coalescedCount || 0),
        errorMessage: result.ok ? '' : errorMessage,
      }).catch((err) => {
        console.warn('report judge realtime refresh analytics failed:', err);
      });
    },
    handleJudgeReportReadyEvent(event) {
      if (!this.shouldHandleSessionEvent(event)) {
        return;
      }
      const sessionId = Number(event.sessionId);
      this.patchRealtimeStats({
        receivedEvents: this.realtimeStats.receivedEvents + 1,
        lastEventType: 'DebateJudgeReportReady',
      });
      this.enqueueRealtimeRefresh(sessionId, 'DebateJudgeReportReady');
    },
    handleDrawVoteResolvedEvent(event) {
      if (!this.shouldHandleSessionEvent(event)) {
        return;
      }
      const sessionId = Number(event.sessionId);
      this.patchRealtimeStats({
        receivedEvents: this.realtimeStats.receivedEvents + 1,
        lastEventType: 'DebateDrawVoteResolved',
      });
      this.enqueueRealtimeRefresh(sessionId, 'DebateDrawVoteResolved');
    },
    async submitVote(agreeDraw) {
      if (!this.canSubmitVote) return;
      const sessionId = normalizeSessionId(this.sessionIdInput);
      if (!sessionId) return;
      this.voteSubmitting = true;
      this.errorText = '';
      try {
        const payload = await this.$store.dispatch('submitDrawVote', {
          sessionId,
          agreeDraw,
        });
        this.drawVoteData = {
          sessionId: payload.sessionId,
          status: payload.status,
          vote: payload.vote,
        };
      } catch (err) {
        this.errorText = this.errorMessage(err);
      } finally {
        this.voteSubmitting = false;
      }
    },
    async loadReport() {
      const sessionId = normalizeSessionId(this.sessionIdInput);
      if (!sessionId) {
        this.errorText = '请输入有效的 session id（正整数）';
        return;
      }
      this.pendingAutoRefresh = null;
      this.clearAutoRefreshTimer();
      this.summaryRows = [];
      this.summaryErrorText = '';
      this.summaryMetricsErrorText = '';
      await this.fetchReportForSession(sessionId);
      await this.loadRefreshSummary(sessionId);
      await this.loadRefreshSummaryMetrics({ silent: true, suppressOnError: true });
    },
    async refreshSummary() {
      const sessionId = normalizeSessionId(this.sessionIdInput);
      if (!sessionId) {
        this.summaryErrorText = '请输入有效的 session id（正整数）';
        return;
      }
      await this.loadRefreshSummary(sessionId);
    },
    async loadMoreStages() {
      if (!this.canLoadMore) return;
      const sessionId = normalizeSessionId(this.sessionIdInput);
      if (!sessionId) return;
      this.loadingMore = true;
      this.errorText = '';
      try {
        const payload = await this.$store.dispatch('fetchJudgeReport', {
          sessionId,
          maxStageCount: this.windowSize,
          stageOffset: this.stageMeta.nextOffset || 0,
        });
        this.reportData = mergeJudgeReportWindow(this.reportData, payload);
      } catch (err) {
        this.errorText = this.errorMessage(err);
      } finally {
        this.loadingMore = false;
      }
    },
  },
};
</script>
