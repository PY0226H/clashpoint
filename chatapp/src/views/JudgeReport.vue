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
import { mergeJudgeReportWindow, normalizeSessionId } from '../judge-report-utils';

export default {
  components: {
    Sidebar,
  },
  data() {
    return {
      sessionIdInput: '',
      reportData: null,
      loading: false,
      loadingMore: false,
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
    canLoadMore() {
      return !!(this.stageMeta && this.stageMeta.hasMore && !this.loadingMore && !this.loading);
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
    errorMessage(err) {
      return err?.response?.data?.error || err?.message || '请求失败';
    },
    async loadReport() {
      const sessionId = normalizeSessionId(this.sessionIdInput);
      if (!sessionId) {
        this.errorText = '请输入有效的 session id（正整数）';
        return;
      }
      this.loading = true;
      this.errorText = '';
      try {
        const payload = await this.$store.dispatch('fetchJudgeReport', {
          sessionId,
          maxStageCount: this.windowSize,
          stageOffset: 0,
        });
        this.reportData = payload;
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
