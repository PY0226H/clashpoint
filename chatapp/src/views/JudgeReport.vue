<template>
  <div class="flex h-screen">
    <Sidebar />
    <div class="flex-1 overflow-y-auto bg-gray-50">
      <div class="max-w-5xl mx-auto p-6 space-y-4">
        <div>
          <h1 class="text-2xl font-bold text-gray-900">AI Judge Report</h1>
          <p class="text-sm text-gray-600 mt-1">
            输入辩论 session id，查看 AI 判决与阶段摘要。
          </p>
        </div>

        <div class="bg-white rounded-lg border p-4 flex gap-3 items-center">
          <input
            v-model="sessionIdInput"
            type="text"
            class="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="例如：123"
          />
          <button
            @click="loadReport"
            :disabled="loading"
            class="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            {{ loading ? '查询中...' : '查询' }}
          </button>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 text-sm border border-red-200 rounded p-3">
          {{ errorText }}
        </div>

        <div v-if="reportData" class="space-y-4">
          <div class="bg-white rounded-lg border p-4">
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

          <div v-if="!report" class="bg-white rounded-lg border p-4 text-sm text-gray-600">
            当前还没有可展示的判决报告（可能仍在处理中）。
          </div>

          <template v-else>
            <div class="bg-white rounded-lg border p-4">
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

            <div v-if="showDrawVoteCard" class="bg-white rounded-lg border p-4 space-y-3">
              <div class="flex items-center justify-between">
                <div class="text-xs uppercase text-gray-500">Draw Vote</div>
                <button
                  @click="refreshDrawVote(reportData.sessionId)"
                  :disabled="drawVoteLoading || voteSubmitting"
                  class="px-3 py-1 rounded border text-xs bg-white hover:bg-gray-100 disabled:opacity-50"
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

            <div class="bg-white rounded-lg border p-4">
              <div class="text-xs uppercase text-gray-500 mb-2">Rationale</div>
              <p class="text-sm text-gray-800 whitespace-pre-wrap">{{ report.rationale }}</p>
            </div>

            <div class="bg-white rounded-lg border p-4">
              <div class="text-xs uppercase text-gray-500 mb-2">RAG</div>
              <div v-if="report.rag" class="text-sm text-gray-700 space-y-1">
                <div>snippetCount: {{ report.rag.snippetCount ?? 0 }}</div>
                <div>sources: {{ (report.rag.sources || []).length }}</div>
                <div>usedByModel: {{ report.rag.usedByModel ? 'true' : 'false' }}</div>
              </div>
              <div v-else class="text-sm text-gray-500">无 RAG 元信息</div>
            </div>

            <div class="bg-white rounded-lg border p-4">
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

<script>
import Sidebar from '../components/Sidebar.vue';
import {
  drawVoteChoiceText as drawVoteChoiceTextLabel,
  drawVoteResolutionText as drawVoteResolutionLabel,
  isDrawVoteOpen,
  mergeJudgeReportWindow,
  normalizeSessionId,
} from '../judge-report-utils';

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
      errorText: '',
      windowSize: 3,
    };
  },
  computed: {
    report() {
      return this.reportData?.report || null;
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
    drawVoteChoiceText(myVote) {
      return drawVoteChoiceTextLabel(myVote);
    },
    drawVoteResolutionText(resolution) {
      return drawVoteResolutionLabel(resolution);
    },
    errorMessage(err) {
      return err?.response?.data?.error || err?.message || '请求失败';
    },
    async refreshDrawVote(sessionId) {
      this.drawVoteLoading = true;
      try {
        const payload = await this.$store.dispatch('fetchDrawVoteStatus', { sessionId });
        this.drawVoteData = payload;
      } finally {
        this.drawVoteLoading = false;
      }
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
      this.loading = true;
      this.errorText = '';
      this.drawVoteData = null;
      try {
        const payload = await this.$store.dispatch('fetchJudgeReport', {
          sessionId,
          maxStageCount: this.windowSize,
          stageOffset: 0,
        });
        this.reportData = payload;
        if (payload?.report) {
          await this.refreshDrawVote(sessionId);
        }
      } catch (err) {
        this.errorText = this.errorMessage(err);
      } finally {
        this.loading = false;
      }
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
