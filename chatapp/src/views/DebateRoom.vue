<template>
  <div class="flex h-screen">
    <Sidebar />
    <div class="flex-1 flex flex-col bg-gray-50 min-h-0">
      <div class="border-b bg-white px-5 py-3 flex items-center justify-between gap-3">
        <div>
          <div class="text-xs uppercase text-gray-500">Debate Room</div>
          <div class="text-lg font-semibold text-gray-900">Session {{ sessionId || '-' }}</div>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-gray-700 bg-gray-100 border border-gray-200 rounded px-2 py-1">
            余额: {{ walletLoading ? '...' : walletBalance }}
          </span>
          <span
            :class="[
              'inline-block w-2.5 h-2.5 rounded-full',
              wsConnected ? 'bg-green-500' : 'bg-gray-400',
            ]"
          />
          <span class="text-xs text-gray-600">{{ wsStatusText }}</span>
          <button
            @click="refreshRoom"
            :disabled="loading"
            class="px-3 py-1.5 text-sm rounded border bg-white hover:bg-gray-100 disabled:opacity-50"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
          <button
            @click="goLobby"
            class="px-3 py-1.5 text-sm rounded bg-blue-600 text-white"
          >
            返回大厅
          </button>
        </div>
      </div>

      <div v-if="errorText" class="mx-5 mt-4 bg-red-50 text-red-700 border border-red-200 rounded p-3 text-sm">
        {{ errorText }}
      </div>
      <div v-if="walletErrorText" class="mx-5 mt-2 bg-amber-50 text-amber-700 border border-amber-200 rounded p-3 text-sm">
        {{ walletErrorText }}
      </div>

      <div class="px-5 pt-4">
        <div class="bg-white border rounded-lg p-4 space-y-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-xs uppercase text-gray-500">AI Judge</div>
              <div class="text-sm text-gray-700">
                status:
                <span class="font-semibold" :class="judgeStatusClass">{{ judgeStatus }}</span>
              </div>
            </div>
            <div class="flex gap-2">
              <button
                @click="refreshJudgeReport"
                :disabled="judgeLoading"
                class="px-3 py-1.5 text-xs rounded border bg-white hover:bg-gray-100 disabled:opacity-50"
              >
                {{ judgeLoading ? '刷新中...' : '刷新状态' }}
              </button>
              <button
                v-if="showManualJudgeTrigger"
                @click="requestJudgeJob"
                :disabled="judgeRequesting"
                class="px-3 py-1.5 text-xs rounded border bg-white hover:bg-gray-100 disabled:opacity-50"
              >
                {{ judgeRequesting ? '请求中...' : '手动补触发（兜底）' }}
              </button>
              <button
                @click="openJudgeReportPage"
                class="px-3 py-1.5 text-xs rounded border bg-white hover:bg-gray-100"
              >
                打开判决详情页
              </button>
            </div>
          </div>

          <div class="text-xs text-gray-600">
            {{ judgeAutomationHint }}
          </div>

          <div v-if="judgeLatestJob" class="text-xs text-gray-600">
            latest job: #{{ judgeLatestJob.jobId }} · {{ judgeLatestJob.status }} ·
            {{ formatDateTime(judgeLatestJob.requestedAt) }}
          </div>

          <div v-if="judgeReport" class="border rounded p-3 bg-gray-50 text-sm space-y-1">
            <div class="font-semibold text-gray-900">
              最新结果：{{ judgeReport.winner }}（Pro {{ judgeReport.proScore }} / Con {{ judgeReport.conScore }}）
            </div>
            <div class="text-gray-700">style: {{ judgeReport.styleMode }} · reportId: {{ judgeReport.reportId }}</div>
            <div v-if="judgeReport.needsDrawVote" class="text-amber-700">
              当前判决需要平局投票，可在下方直接投票，或进入判决详情页查看完整信息。
            </div>
          </div>

          <div v-if="showDrawVoteCard" class="border rounded p-3 bg-amber-50 text-sm space-y-2">
            <div class="flex items-center justify-between gap-2">
              <div class="font-semibold text-amber-900">平局投票</div>
              <button
                @click="refreshDrawVote"
                :disabled="drawVoteLoading || voteSubmitting"
                class="px-2 py-1 text-xs rounded border bg-white hover:bg-gray-100 disabled:opacity-50"
              >
                {{ drawVoteLoading ? '刷新中...' : '刷新投票状态' }}
              </button>
            </div>

            <div v-if="!drawVote" class="text-xs text-gray-700">
              当前没有可用的平局投票信息。
            </div>

            <template v-else>
              <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-gray-700">
                <div>状态：<span :class="drawVoteStatusClass">{{ drawVoteStatus }}</span></div>
                <div>参与/门槛：{{ drawVote.participatedVoters }} / {{ drawVote.requiredVoters }}</div>
                <div>同意/不同意：{{ drawVote.agreeVotes }} / {{ drawVote.disagreeVotes }}</div>
                <div>我的投票：{{ drawVoteChoiceText(drawVote.myVote) }}</div>
              </div>
              <div class="text-xs text-gray-700">
                投票截止：{{ formatDateTime(drawVote.votingEndsAt) }}
              </div>
              <div class="text-xs text-gray-700">
                判定来源：{{ drawVoteDecisionSourceText(drawVote.decisionSource) }}
              </div>
              <div v-if="drawVoteStatus === 'open'" class="text-xs text-gray-700">
                剩余时间：{{ drawVoteRemainingText }}
              </div>
              <div v-if="canSubmitDrawVote" class="flex flex-wrap gap-2">
                <button
                  @click="submitDrawVote(true)"
                  :disabled="voteSubmitting"
                  class="px-3 py-1.5 text-xs rounded bg-green-600 text-white disabled:opacity-50"
                >
                  {{ voteSubmitting ? '提交中...' : '同意平局（不二番战）' }}
                </button>
                <button
                  @click="submitDrawVote(false)"
                  :disabled="voteSubmitting"
                  class="px-3 py-1.5 text-xs rounded bg-orange-600 text-white disabled:opacity-50"
                >
                  {{ voteSubmitting ? '提交中...' : '不同意平局（开启二番战）' }}
                </button>
              </div>
              <div v-else class="text-xs text-gray-700">
                {{ drawVoteResolutionText(drawVote.resolution) }}
                <span v-if="drawVote.rematchSessionId">，二番战 session: {{ drawVote.rematchSessionId }}</span>
              </div>
            </template>

            <div v-if="drawVoteErrorText" class="text-xs text-red-700">
              {{ drawVoteErrorText }}
            </div>
          </div>

          <div v-if="judgeErrorText" class="text-xs text-red-700">
            {{ judgeErrorText }}
          </div>
        </div>
      </div>

      <div class="px-5 py-3">
        <div class="text-xs uppercase text-gray-500 mb-2">置顶消息</div>
        <div v-if="pins.length === 0" class="text-sm text-gray-500 bg-white rounded border p-3">
          当前没有有效置顶消息
        </div>
        <div v-else class="flex flex-col gap-2 max-h-40 overflow-y-auto pr-1">
          <div
            v-for="pin in pins"
            :key="pin.id"
            class="bg-white border rounded p-3 text-sm"
          >
            <div class="flex items-center justify-between">
              <div class="font-semibold text-gray-900">
                {{ pin.side }} · user {{ pin.userId }} · {{ pin.costCoins }} coins
              </div>
              <div class="text-xs text-gray-500">
                到期 {{ formatDateTime(pin.expiresAt) }}
              </div>
            </div>
            <div class="text-gray-700 mt-1 whitespace-pre-wrap">{{ pin.content }}</div>
          </div>
        </div>
      </div>

      <div class="flex-1 min-h-0 px-5 pb-4">
        <div class="text-xs uppercase text-gray-500 mb-2">发言流</div>
        <div class="bg-white border rounded-lg h-full flex flex-col min-h-0">
          <div ref="messageScrollBox" class="flex-1 overflow-y-auto p-3 space-y-2">
            <div v-if="historyHasMore" class="flex justify-center pb-2">
              <button
                @click="loadOlderMessages"
                :disabled="historyLoading || loading"
                class="px-3 py-1.5 text-xs rounded border bg-white hover:bg-gray-100 disabled:opacity-50"
              >
                {{ historyLoading ? '加载中...' : '加载更早消息' }}
              </button>
            </div>
            <div v-if="messages.length === 0" class="text-sm text-gray-500">
              当前暂无消息
            </div>
            <div
              v-for="message in messages"
              :key="message.id"
              class="rounded border p-3"
              :class="isOwnMessage(message) ? 'border-blue-200 bg-blue-50' : 'border-gray-200 bg-gray-50'"
            >
              <div class="flex items-center justify-between mb-1">
                <div class="text-xs text-gray-600">
                  {{ message.side }} · user {{ message.userId }}
                </div>
                <div class="text-xs text-gray-500">
                  {{ formatDateTime(message.createdAt) }}
                </div>
              </div>
              <div class="text-sm text-gray-800 whitespace-pre-wrap">{{ message.content }}</div>
              <div v-if="isOwnMessage(message)" class="mt-2 flex items-center gap-2">
                <select
                  v-model.number="pinSeconds"
                  class="border rounded px-2 py-1 text-xs"
                >
                  <option :value="30">30s</option>
                  <option :value="60">60s</option>
                  <option :value="90">90s</option>
                  <option :value="120">120s</option>
                  <option :value="180">180s</option>
                  <option :value="300">300s</option>
                  <option :value="600">600s</option>
                </select>
                <button
                  @click="pinMessage(message)"
                  :disabled="pinningMessageId === message.id"
                  class="px-2 py-1 text-xs rounded bg-indigo-600 text-white disabled:opacity-50"
                >
                  {{ pinningMessageId === message.id ? '置顶中...' : '置顶' }}
                </button>
              </div>
            </div>
          </div>

          <div class="border-t p-3">
            <div class="flex gap-2">
              <textarea
                v-model="messageInput"
                rows="2"
                class="flex-1 border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="输入你的辩论发言..."
              />
              <button
                @click="sendMessage"
                :disabled="sending"
                class="px-4 py-2 h-fit rounded bg-blue-600 text-white text-sm disabled:opacity-50"
              >
                {{ sending ? '发送中...' : '发送' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from '../components/Sidebar.vue';
import { getNotifyBase } from '../utils';
import {
  drawVoteChoiceText as drawVoteChoiceTextLabel,
  drawVoteDecisionSourceText as drawVoteDecisionSourceTextLabel,
  drawVoteResolutionText as drawVoteResolutionTextLabel,
} from '../judge-report-utils';
import {
  buildDebateRoomWsUrl,
  canSubmitDrawVote as canSubmitDrawVoteNow,
  computeWsReconnectDelayMs,
  extractDebateRoomEvent,
  getDrawVoteRemainingMs,
  getOldestDebateMessageId,
  judgeAutomationHintText,
  mergeDebateRoomMessages,
  normalizeDebateRoomMessage,
  normalizeDrawVoteStatus,
  normalizeJudgeReportStatus,
  parseDebateRoomWsMessage,
  shouldShowManualJudgeTrigger,
  shouldPollJudgeReportStatus,
} from '../debate-room-utils';

const WS_HEARTBEAT_SEND_INTERVAL_MS = 20_000;
const WS_HEARTBEAT_WATCHDOG_INTERVAL_MS = 5_000;
const WS_HEARTBEAT_STALE_TIMEOUT_MS = 65_000;

export default {
  components: {
    Sidebar,
  },
  data() {
    return {
      sessionId: null,
      messages: [],
      pins: [],
      loading: false,
      historyLoading: false,
      historyHasMore: true,
      historyLimit: 80,
      sending: false,
      pinningMessageId: null,
      messageInput: '',
      pinSeconds: 60,
      walletBalance: 0,
      walletLoading: false,
      walletErrorText: '',
      errorText: '',
      ws: null,
      wsConnected: false,
      wsReconnectTimer: null,
      wsReconnectAttempts: 0,
      wsHeartbeatTimer: null,
      wsHeartbeatWatchdogTimer: null,
      wsLastMessageAt: 0,
      lastAckSeq: 0,
      roomRecovering: false,
      lastRoomRecoverAt: 0,
      judgeLoading: false,
      judgeRequesting: false,
      judgeErrorText: '',
      judgeResult: null,
      drawVoteData: null,
      drawVoteLoading: false,
      voteSubmitting: false,
      drawVoteErrorText: '',
      judgePollTimer: null,
      nowMs: Date.now(),
      clockTimer: null,
      drawVoteDeadlineRefreshTriggered: false,
      destroyed: false,
    };
  },
  computed: {
    userId() {
      return this.$store.state.user?.id || null;
    },
    judgeStatus() {
      return normalizeJudgeReportStatus(this.judgeResult?.status);
    },
    judgeLatestJob() {
      return this.judgeResult?.latestJob || null;
    },
    judgeReport() {
      return this.judgeResult?.report || null;
    },
    drawVote() {
      return this.drawVoteData?.vote || null;
    },
    drawVoteStatus() {
      return normalizeDrawVoteStatus(this.drawVote?.status);
    },
    drawVoteRemainingMs() {
      return getDrawVoteRemainingMs(this.drawVote, this.nowMs);
    },
    drawVoteRemainingText() {
      return this.formatRemainingMs(this.drawVoteRemainingMs);
    },
    drawVoteStatusClass() {
      if (this.drawVoteStatus === 'open') {
        return 'text-amber-700';
      }
      if (this.drawVoteStatus === 'decided') {
        return 'text-green-700';
      }
      if (this.drawVoteStatus === 'expired') {
        return 'text-gray-700';
      }
      return 'text-gray-700';
    },
    showDrawVoteCard() {
      return !!(this.judgeReport?.needsDrawVote || this.drawVote);
    },
    canSubmitDrawVote() {
      return canSubmitDrawVoteNow(this.drawVote, this.nowMs) && !this.voteSubmitting;
    },
    judgeStatusClass() {
      if (this.judgeStatus === 'ready') {
        return 'text-green-700';
      }
      if (this.judgeStatus === 'pending') {
        return 'text-amber-700';
      }
      if (this.judgeStatus === 'failed') {
        return 'text-red-700';
      }
      return 'text-gray-700';
    },
    showManualJudgeTrigger() {
      return shouldShowManualJudgeTrigger(this.judgeStatus);
    },
    judgeAutomationHint() {
      return judgeAutomationHintText(this.judgeStatus);
    },
    wsStatusText() {
      if (this.wsConnected) {
        return 'WS Connected';
      }
      if (this.wsReconnectTimer) {
        return `WS Reconnecting (#${this.wsReconnectAttempts})`;
      }
      return 'WS Disconnected';
    },
  },
  methods: {
    parseSessionId() {
      const parsed = Number(this.$route.params.id);
      if (!parsed || Number.isNaN(parsed)) {
        throw new Error('invalid session id');
      }
      this.sessionId = parsed;
      this.restoreLastAckSeq();
    },
    lastAckSeqStorageKey() {
      if (!this.sessionId) {
        return '';
      }
      return `debateRoom:lastAckSeq:${this.sessionId}`;
    },
    restoreLastAckSeq() {
      const key = this.lastAckSeqStorageKey();
      if (!key || !globalThis?.sessionStorage) {
        this.lastAckSeq = 0;
        return;
      }
      const raw = Number(globalThis.sessionStorage.getItem(key));
      this.lastAckSeq = Number.isFinite(raw) && raw >= 0 ? Math.floor(raw) : 0;
    },
    persistLastAckSeq() {
      const key = this.lastAckSeqStorageKey();
      if (!key || !globalThis?.sessionStorage) {
        return;
      }
      globalThis.sessionStorage.setItem(key, String(this.lastAckSeq));
    },
    setLastAckSeq(seq) {
      const next = Number(seq);
      if (!Number.isFinite(next) || next < 0) {
        return;
      }
      const normalized = Math.floor(next);
      if (normalized <= this.lastAckSeq) {
        return;
      }
      this.lastAckSeq = normalized;
      this.persistLastAckSeq();
    },
    formatDateTime(value) {
      if (!value) {
        return '-';
      }
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString();
    },
    formatRemainingMs(ms) {
      if (!Number.isFinite(ms)) {
        return '-';
      }
      const totalSeconds = Math.max(0, Math.floor(ms / 1000));
      const hours = Math.floor(totalSeconds / 3600);
      const minutes = Math.floor((totalSeconds % 3600) / 60);
      const seconds = totalSeconds % 60;
      if (hours > 0) {
        return `${hours}h ${String(minutes).padStart(2, '0')}m ${String(seconds).padStart(2, '0')}s`;
      }
      return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    },
    startClock() {
      if (this.clockTimer) {
        return;
      }
      this.clockTimer = setInterval(() => {
        this.nowMs = Date.now();
        if (
          this.drawVoteStatus === 'open' &&
          Number.isFinite(this.drawVoteRemainingMs) &&
          this.drawVoteRemainingMs <= 0 &&
          !this.drawVoteDeadlineRefreshTriggered
        ) {
          this.drawVoteDeadlineRefreshTriggered = true;
          this.refreshDrawVote({ silent: true });
        }
      }, 1000);
    },
    stopClock() {
      if (!this.clockTimer) {
        return;
      }
      clearInterval(this.clockTimer);
      this.clockTimer = null;
    },
    drawVoteChoiceText(myVote) {
      return drawVoteChoiceTextLabel(myVote);
    },
    drawVoteDecisionSourceText(decisionSource) {
      return drawVoteDecisionSourceTextLabel(decisionSource);
    },
    drawVoteResolutionText(resolution) {
      return drawVoteResolutionTextLabel(resolution);
    },
    isOwnMessage(message) {
      return Number(message.userId) === Number(this.userId);
    },
    upsertMessage(raw) {
      const normalized = normalizeDebateRoomMessage(raw);
      if (!normalized) {
        return;
      }
      this.messages = mergeDebateRoomMessages(this.messages, [normalized]);
    },
    async refreshRoom() {
      if (!this.sessionId) {
        return;
      }
      this.loading = true;
      this.errorText = '';
      try {
        const [messages, pins, wallet] = await Promise.all([
          this.$store.dispatch('listDebateMessages', {
            sessionId: this.sessionId,
            limit: this.historyLimit,
          }),
          this.$store.dispatch('listDebatePinnedMessages', {
            sessionId: this.sessionId,
            activeOnly: true,
            limit: 30,
          }),
          this.$store.dispatch('fetchWalletBalance'),
        ]);
        this.messages = mergeDebateRoomMessages([], messages || []);
        this.historyHasMore = Array.isArray(messages) && messages.length >= this.historyLimit;
        this.pins = pins;
        this.walletBalance = Number(wallet?.balance || 0);
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '加载辩论房间失败';
      } finally {
        this.loading = false;
      }
    },
    async loadOlderMessages() {
      if (!this.sessionId || this.historyLoading || !this.historyHasMore) {
        return;
      }
      const oldestId = getOldestDebateMessageId(this.messages);
      if (!oldestId) {
        this.historyHasMore = false;
        return;
      }

      this.historyLoading = true;
      this.errorText = '';
      const box = this.$refs.messageScrollBox;
      const beforeHeight = box?.scrollHeight || 0;
      const beforeTop = box?.scrollTop || 0;
      try {
        const older = await this.$store.dispatch('listDebateMessages', {
          sessionId: this.sessionId,
          lastId: oldestId,
          limit: this.historyLimit,
        });
        const list = Array.isArray(older) ? older : [];
        if (list.length === 0) {
          this.historyHasMore = false;
          return;
        }
        this.messages = mergeDebateRoomMessages(this.messages, list);
        this.historyHasMore = list.length >= this.historyLimit;
        this.$nextTick(() => {
          const nextBox = this.$refs.messageScrollBox;
          if (!nextBox) {
            return;
          }
          const afterHeight = nextBox.scrollHeight || 0;
          nextBox.scrollTop = Math.max(0, afterHeight - beforeHeight + beforeTop);
        });
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '加载历史消息失败';
      } finally {
        this.historyLoading = false;
      }
    },
    handleRoomPayload(payload) {
      const event = payload?.event;
      if (event === 'DebateMessageCreated') {
        this.upsertMessage({
          id: payload.messageId,
          sessionId: payload.sessionId,
          userId: payload.userId,
          side: payload.side,
          content: payload.content,
          createdAt: payload.createdAt,
        });
        return;
      }
      if (event === 'DebateMessagePinned') {
        this.refreshPins();
        return;
      }
      if (event === 'DebateJudgeReportReady' || event === 'DebateDrawVoteResolved') {
        this.refreshJudgeReport({ silent: true });
        this.refreshDrawVote({ silent: true });
      }
    },
    clearJudgePollTimer() {
      if (this.judgePollTimer) {
        clearTimeout(this.judgePollTimer);
        this.judgePollTimer = null;
      }
    },
    scheduleJudgePoll(delayMs = 8000) {
      this.clearJudgePollTimer();
      if (this.destroyed) {
        return;
      }
      this.judgePollTimer = setTimeout(() => {
        this.judgePollTimer = null;
        this.refreshJudgeReport({ silent: true });
      }, Math.max(1000, Number(delayMs) || 0));
    },
    async refreshJudgeReport({ silent = false } = {}) {
      if (!this.sessionId) {
        return;
      }
      if (!silent) {
        this.judgeLoading = true;
      }
      this.judgeErrorText = '';
      try {
        const payload = await this.$store.dispatch('fetchJudgeReport', {
          sessionId: this.sessionId,
          maxStageCount: 1,
          stageOffset: 0,
        });
        this.judgeResult = payload || null;
        if (normalizeJudgeReportStatus(payload?.status) === 'ready' || this.drawVoteData?.vote) {
          this.refreshDrawVote({ silent: true });
        }
        if (shouldPollJudgeReportStatus(payload?.status)) {
          this.scheduleJudgePoll(8000);
        } else {
          this.clearJudgePollTimer();
        }
      } catch (error) {
        if (!silent) {
          this.judgeErrorText = error?.response?.data?.error || error?.message || '查询判决状态失败';
        }
        this.scheduleJudgePoll(10000);
      } finally {
        if (!silent) {
          this.judgeLoading = false;
        }
      }
    },
    async refreshDrawVote({ silent = false } = {}) {
      if (!this.sessionId) {
        return;
      }
      if (!silent) {
        this.drawVoteLoading = true;
      }
      this.drawVoteErrorText = '';
      try {
        const payload = await this.$store.dispatch('fetchDrawVoteStatus', {
          sessionId: this.sessionId,
        });
        this.drawVoteData = payload || null;
        if (normalizeDrawVoteStatus(this.drawVote?.status) === 'open') {
          const remaining = getDrawVoteRemainingMs(this.drawVote, this.nowMs);
          if (!Number.isFinite(remaining) || remaining > 0) {
            this.drawVoteDeadlineRefreshTriggered = false;
          }
        } else {
          this.drawVoteDeadlineRefreshTriggered = false;
        }
      } catch (error) {
        if (!silent) {
          this.drawVoteErrorText = error?.response?.data?.error || error?.message || '刷新投票状态失败';
        }
      } finally {
        if (!silent) {
          this.drawVoteLoading = false;
        }
      }
    },
    async submitDrawVote(agreeDraw) {
      if (!this.canSubmitDrawVote) {
        return;
      }
      this.voteSubmitting = true;
      this.drawVoteErrorText = '';
      try {
        const payload = await this.$store.dispatch('submitDrawVote', {
          sessionId: this.sessionId,
          agreeDraw,
        });
        this.drawVoteData = {
          sessionId: payload.sessionId,
          status: payload.status,
          vote: payload.vote,
        };
        await this.refreshJudgeReport({ silent: true });
      } catch (error) {
        this.drawVoteErrorText = error?.response?.data?.error || error?.message || '提交投票失败';
      } finally {
        this.voteSubmitting = false;
      }
    },
    async requestJudgeJob() {
      if (!this.sessionId) {
        return;
      }
      this.judgeRequesting = true;
      this.judgeErrorText = '';
      try {
        await this.$store.dispatch('requestJudgeJob', {
          sessionId: this.sessionId,
          allowRejudge: false,
        });
        await this.refreshJudgeReport({ silent: true });
      } catch (error) {
        this.judgeErrorText = error?.response?.data?.error || error?.message || '发起判决失败';
      } finally {
        this.judgeRequesting = false;
      }
    },
    async openJudgeReportPage() {
      if (!this.sessionId) {
        return;
      }
      await this.$router.push({
        path: '/judge-report',
        query: { sessionId: String(this.sessionId) },
      });
    },
    clearWsReconnectTimer() {
      if (this.wsReconnectTimer) {
        clearTimeout(this.wsReconnectTimer);
        this.wsReconnectTimer = null;
      }
    },
    markWsActivity() {
      this.wsLastMessageAt = Date.now();
    },
    clearWsHeartbeatTimers() {
      if (this.wsHeartbeatTimer) {
        clearInterval(this.wsHeartbeatTimer);
        this.wsHeartbeatTimer = null;
      }
      if (this.wsHeartbeatWatchdogTimer) {
        clearInterval(this.wsHeartbeatWatchdogTimer);
        this.wsHeartbeatWatchdogTimer = null;
      }
    },
    startWsHeartbeat(ws) {
      this.clearWsHeartbeatTimers();
      this.markWsActivity();
      this.wsHeartbeatTimer = setInterval(() => {
        if (this.destroyed || this.ws !== ws || ws.readyState !== WebSocket.OPEN) {
          return;
        }
        try {
          ws.send(JSON.stringify({ type: 'ping' }));
        } catch (_) {
          ws.close();
        }
      }, WS_HEARTBEAT_SEND_INTERVAL_MS);
      this.wsHeartbeatWatchdogTimer = setInterval(() => {
        if (this.destroyed || this.ws !== ws || ws.readyState !== WebSocket.OPEN) {
          return;
        }
        if (Date.now() - this.wsLastMessageAt > WS_HEARTBEAT_STALE_TIMEOUT_MS) {
          ws.close();
        }
      }, WS_HEARTBEAT_WATCHDOG_INTERVAL_MS);
    },
    handleWsControlMessage(ws, msg) {
      const type = String(msg?.type || '');
      if (!type) {
        return false;
      }
      this.markWsActivity();
      if (type === 'ping') {
        if (this.ws === ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'pong' }));
        }
        return true;
      }
      if (type === 'welcome') {
        return true;
      }
      if (type === 'pong') {
        return true;
      }
      if (type === 'syncRequired') {
        this.disconnectWs();
        this.connectRoomWs();
        return true;
      }
      return false;
    },
    handleRoomEventMessage(msg) {
      const eventSeqRaw = Number(msg?.eventSeq ?? msg?.event_seq);
      if (Number.isFinite(eventSeqRaw) && eventSeqRaw > 0) {
        const eventSeq = Math.floor(eventSeqRaw);
        if (eventSeq <= this.lastAckSeq) {
          return;
        }
        if (eventSeq > this.lastAckSeq + 1) {
          this.disconnectWs();
          this.connectRoomWs();
          return;
        }
        const payload = extractDebateRoomEvent(msg);
        if (payload) {
          this.handleRoomPayload(payload);
        }
        this.setLastAckSeq(eventSeq);
        return;
      }
      const payload = extractDebateRoomEvent(msg);
      if (payload) {
        this.handleRoomPayload(payload);
      }
    },
    scheduleWsReconnect() {
      if (this.destroyed || this.wsReconnectTimer) {
        return;
      }
      this.wsReconnectAttempts += 1;
      const delayMs = computeWsReconnectDelayMs(this.wsReconnectAttempts);
      this.wsReconnectTimer = setTimeout(() => {
        this.wsReconnectTimer = null;
        this.connectRoomWs();
      }, delayMs);
    },
    disconnectWs({ resetBackoff = false } = {}) {
      this.clearWsReconnectTimer();
      this.clearWsHeartbeatTimers();
      if (this.ws) {
        this.ws.close();
      }
      this.ws = null;
      this.wsConnected = false;
      if (resetBackoff) {
        this.wsReconnectAttempts = 0;
      }
    },
    async recoverRoomStateAfterReconnect() {
      if (!this.sessionId || this.roomRecovering) {
        return;
      }
      const now = Date.now();
      if (now - this.lastRoomRecoverAt < 3000) {
        return;
      }
      this.roomRecovering = true;
      try {
        const [messages, pins] = await Promise.all([
          this.$store.dispatch('listDebateMessages', {
            sessionId: this.sessionId,
            limit: this.historyLimit,
          }),
          this.$store.dispatch('listDebatePinnedMessages', {
            sessionId: this.sessionId,
            activeOnly: true,
            limit: 30,
          }),
        ]);
        this.messages = mergeDebateRoomMessages(this.messages, messages || []);
        this.historyHasMore = Array.isArray(messages) && messages.length >= this.historyLimit;
        this.pins = pins;
        await Promise.all([
          this.refreshJudgeReport({ silent: true }),
          this.refreshDrawVote({ silent: true }),
          this.refreshWalletBalance({ silent: true }),
        ]);
      } catch (_) {
        // Keep websocket reconnect recovery non-blocking.
      } finally {
        this.lastRoomRecoverAt = Date.now();
        this.roomRecovering = false;
      }
    },
    async connectRoomWs() {
      if (this.destroyed || !this.sessionId) {
        return;
      }
      try {
        await this.$store.dispatch('refreshAccessTickets');
        const notifyTicket = this.$store.state.accessTickets?.notifyToken;
        if (!notifyTicket) {
          this.scheduleWsReconnect();
          return;
        }
        const wsUrl = buildDebateRoomWsUrl({
          notifyBase: getNotifyBase(),
          sessionId: this.sessionId,
          notifyTicket,
          lastAckSeq: this.lastAckSeq,
        });
        this.disconnectWs();
        const ws = new WebSocket(wsUrl);
        this.ws = ws;
        ws.onopen = () => {
          if (this.ws !== ws) {
            return;
          }
          this.wsConnected = true;
          this.wsReconnectAttempts = 0;
          this.startWsHeartbeat(ws);
          this.recoverRoomStateAfterReconnect();
        };
        ws.onmessage = (event) => {
          const msg = parseDebateRoomWsMessage(event?.data);
          if (!msg || typeof msg !== 'object') {
            return;
          }
          if (this.handleWsControlMessage(ws, msg)) {
            return;
          }
          this.handleRoomEventMessage(msg);
        };
        ws.onerror = () => {
          if (this.ws !== ws) {
            return;
          }
          ws.close();
        };
        ws.onclose = () => {
          if (this.ws !== ws) {
            return;
          }
          this.ws = null;
          this.wsConnected = false;
          this.clearWsHeartbeatTimers();
          this.scheduleWsReconnect();
        };
      } catch (error) {
        this.wsConnected = false;
        this.scheduleWsReconnect();
      }
    },
    async refreshPins() {
      if (!this.sessionId) {
        return;
      }
      try {
        this.pins = await this.$store.dispatch('listDebatePinnedMessages', {
          sessionId: this.sessionId,
          activeOnly: true,
          limit: 30,
        });
      } catch (_) {
        // Keep current room usable even if pin list refresh fails.
      }
    },
    async refreshWalletBalance({ silent = false } = {}) {
      if (silent !== true) {
        this.walletLoading = true;
      }
      this.walletErrorText = '';
      try {
        const payload = await this.$store.dispatch('fetchWalletBalance');
        this.walletBalance = Number(payload?.balance || 0);
      } catch (error) {
        this.walletErrorText = error?.response?.data?.error || error?.message || '刷新余额失败';
      } finally {
        if (silent !== true) {
          this.walletLoading = false;
        }
      }
    },
    async sendMessage() {
      if (!this.messageInput.trim() || !this.sessionId) {
        return;
      }
      this.sending = true;
      this.errorText = '';
      try {
        const created = await this.$store.dispatch('createDebateMessage', {
          sessionId: this.sessionId,
          content: this.messageInput,
        });
        this.upsertMessage(created);
        this.messageInput = '';
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '发送失败';
      } finally {
        this.sending = false;
      }
    },
    buildPinIdempotencyKey(messageId) {
      if (globalThis?.crypto?.randomUUID) {
        return `pin-${messageId}-${globalThis.crypto.randomUUID()}`;
      }
      return `pin-${messageId}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    },
    async pinMessage(message) {
      if (!message?.id) {
        return;
      }
      this.errorText = '';
      this.pinningMessageId = message.id;
      try {
        await this.$store.dispatch('pinDebateMessage', {
          messageId: message.id,
          pinSeconds: this.pinSeconds,
          idempotencyKey: this.buildPinIdempotencyKey(message.id),
        });
        await Promise.all([this.refreshPins(), this.refreshWalletBalance({ silent: true })]);
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '置顶失败';
      } finally {
        this.pinningMessageId = null;
      }
    },
    async goLobby() {
      await this.$router.push('/debate');
    },
  },
  async mounted() {
    try {
      this.startClock();
      this.parseSessionId();
      await this.refreshRoom();
      await this.refreshJudgeReport({ silent: true });
      await this.connectRoomWs();
    } catch (error) {
      this.errorText = error?.message || '初始化失败';
    }
  },
  beforeUnmount() {
    this.destroyed = true;
    this.stopClock();
    this.clearJudgePollTimer();
    this.disconnectWs({ resetBackoff: true });
  },
};
</script>
