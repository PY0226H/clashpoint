<template>
  <div class="flex h-screen echo-shell">
    <Sidebar />
    <div class="echo-main">
      <div class="max-w-6xl mx-auto p-6 lg:p-8 space-y-4 echo-fade-in">
        <div class="echo-panel-strong p-5 flex items-start justify-between gap-3">
          <div>
            <div class="text-[11px] uppercase tracking-[0.26em] text-slate-500">Debate Lobby</div>
            <h1 class="text-2xl font-semibold text-slate-900 mt-1">辩论场次总览</h1>
            <p class="text-sm text-slate-600 mt-1">按“进行中/待开启”分流：进行中可观战，待开启可选阵营加入。</p>
          </div>
          <button
            @click="refreshLobby"
            :disabled="loading"
            class="echo-btn-primary disabled:opacity-60"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 border border-red-200 rounded-xl p-3 text-sm">
          {{ errorText }}
        </div>
        <div v-if="guardNoticeText" class="bg-amber-50 text-amber-800 border border-amber-200 rounded-xl p-3 text-sm">
          {{ guardNoticeText }}
        </div>

        <div class="echo-panel p-4 grid grid-cols-1 md:grid-cols-6 gap-3">
          <div>
            <div class="text-xs uppercase text-slate-500 mb-1">Topic</div>
            <select
              v-model="selectedTopicId"
              class="echo-field"
            >
              <option value="">全部辩题</option>
              <option v-for="topic in topics" :key="topic.id" :value="String(topic.id)">
                {{ topic.title }}
              </option>
            </select>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500 mb-1">Status</div>
            <select
              v-model="statusFilter"
              class="echo-field"
            >
              <option value="all">全部</option>
              <option value="joinable">可加入</option>
              <option value="live">live</option>
              <option value="upcoming">scheduled</option>
              <option value="open">open</option>
              <option value="running">running</option>
              <option value="ended">ended</option>
            </select>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500 mb-1">Lane</div>
            <select
              v-model="laneFilter"
              class="echo-field"
            >
              <option value="all">全部分区</option>
              <option value="live">进行中</option>
              <option value="upcoming">待开启</option>
              <option value="ended">已结束</option>
            </select>
          </div>
          <div>
            <div class="text-xs uppercase text-slate-500 mb-1">Keyword</div>
            <input
              v-model.trim="keyword"
              class="echo-field"
              placeholder="按辩题关键词筛选"
            />
          </div>
          <label class="inline-flex items-center gap-2 text-xs text-slate-700 self-end">
            <input v-model="joinableOnly" type="checkbox" class="rounded border-gray-300" />
            仅可加入
          </label>
          <div class="text-xs text-slate-500 self-end text-right">
            sessions: {{ filteredSessions.length }} / {{ sessions.length }}
          </div>
        </div>

        <div v-if="searchActionSessions.length > 0" class="echo-panel-strong p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-slate-900">搜索命中快速操作</div>
            <div class="text-xs text-slate-500">hits: {{ searchActionSessions.length }}</div>
          </div>
          <div class="space-y-2">
            <div
              v-for="session in searchActionSessions"
              :key="`search-hit-${session.id}`"
              class="border rounded-xl p-3 bg-white/80 border-slate-200 flex flex-wrap items-center justify-between gap-2"
            >
              <div>
                <div class="text-sm font-semibold text-slate-900">
                  Session {{ session.id }} · {{ topicTitle(sessionTopicId(session)) }}
                </div>
                <div class="text-xs text-slate-600 mt-1">
                  status={{ session.status }} · lane={{ getSessionLane(session) }}
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <button
                  v-if="getSessionLane(session) === 'live'"
                  @click="enterRoom(session.id)"
                  class="echo-btn-secondary"
                >
                  一键观战
                </button>
                <template v-else-if="getSessionLane(session) === 'upcoming'">
                  <button
                    @click="joinAndEnter(session, 'pro')"
                    :disabled="loading || !session.joinable"
                    class="echo-btn-primary disabled:opacity-60"
                  >
                    加入正方
                  </button>
                  <button
                    @click="joinAndEnter(session, 'con')"
                    :disabled="loading || !session.joinable"
                    class="px-3 py-2 rounded-xl bg-orange-600 text-white text-sm font-semibold hover:bg-orange-700 transition disabled:opacity-50"
                  >
                    加入反方
                  </button>
                </template>
                <button
                  v-else
                  @click="enterRoom(session.id)"
                  class="echo-btn-secondary"
                >
                  查看房间
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div class="echo-panel p-3">
            <div class="text-xs uppercase text-slate-500">进行中（观战）</div>
            <div class="text-xl font-semibold text-slate-900 mt-1">{{ liveSessions.length }}</div>
          </div>
          <div class="echo-panel p-3">
            <div class="text-xs uppercase text-slate-500">待开启（可加入）</div>
            <div class="text-xl font-semibold text-slate-900 mt-1">{{ upcomingSessions.length }}</div>
          </div>
          <div class="echo-panel p-3">
            <div class="text-xs uppercase text-slate-500">已结束</div>
            <div class="text-xl font-semibold text-slate-900 mt-1">{{ endedSessions.length }}</div>
          </div>
        </div>

        <div v-if="!hasAnyVisibleSessions" class="echo-panel p-5 text-sm text-slate-600">
          当前筛选下没有可用场次。
        </div>

        <div v-else class="space-y-4">
          <div v-if="liveSessions.length > 0" class="echo-panel-strong p-4 space-y-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-slate-900">进行中（可观战）</div>
              <div class="text-xs text-slate-500">count: {{ liveSessions.length }}</div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div
                v-for="session in liveSessions"
                :key="`live-${session.id}`"
                class="rounded-xl border p-4 space-y-3 bg-white/85 border-slate-200"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs uppercase text-slate-500">Session {{ session.id }}</div>
                    <div class="font-semibold text-slate-900">{{ topicTitle(sessionTopicId(session)) }}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-xs uppercase text-slate-500">Status</div>
                    <div class="text-sm font-semibold text-slate-900">{{ session.status }}</div>
                  </div>
                </div>

                <div class="text-xs text-slate-500">
                  开始: {{ formatDateTime(session.scheduledStartAt) }} |
                  结束: {{ formatDateTime(session.endAt) }}
                </div>

                <div class="text-sm text-slate-700 flex gap-3">
                  <span>Pro: <strong>{{ session.proCount }}</strong></span>
                  <span>Con: <strong>{{ session.conCount }}</strong></span>
                  <span>Hot: <strong>{{ session.hotScore }}</strong></span>
                </div>

                <div class="flex flex-wrap gap-2">
                  <button
                    @click="enterRoom(session.id)"
                    class="echo-btn-secondary"
                  >
                    观战房间
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="upcomingSessions.length > 0" class="echo-panel-strong p-4 space-y-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-slate-900">待开启（可加入）</div>
              <div class="text-xs text-slate-500">count: {{ upcomingSessions.length }}</div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div
                v-for="session in upcomingSessions"
                :key="`upcoming-${session.id}`"
                class="rounded-xl border p-4 space-y-3 bg-white/85 border-slate-200"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs uppercase text-slate-500">Session {{ session.id }}</div>
                    <div class="font-semibold text-slate-900">{{ topicTitle(sessionTopicId(session)) }}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-xs uppercase text-slate-500">Status</div>
                    <div class="text-sm font-semibold text-slate-900">{{ session.status }}</div>
                  </div>
                </div>

                <div class="text-xs text-slate-500">
                  开始: {{ formatDateTime(session.scheduledStartAt) }} |
                  结束: {{ formatDateTime(session.endAt) }}
                </div>

                <div class="text-sm text-slate-700 flex gap-3">
                  <span>Pro: <strong>{{ session.proCount }}</strong></span>
                  <span>Con: <strong>{{ session.conCount }}</strong></span>
                  <span>Hot: <strong>{{ session.hotScore }}</strong></span>
                </div>

                <div class="flex flex-wrap gap-2">
                  <button
                    @click="joinAndEnter(session, 'pro')"
                    :disabled="loading || !session.joinable"
                    class="echo-btn-primary disabled:opacity-60"
                  >
                    加入正方
                  </button>
                  <button
                    @click="joinAndEnter(session, 'con')"
                    :disabled="loading || !session.joinable"
                    class="px-3 py-2 rounded-xl bg-orange-600 text-white text-sm font-semibold hover:bg-orange-700 transition disabled:opacity-50"
                  >
                    加入反方
                  </button>
                  <button
                    @click="enterRoom(session.id)"
                    class="echo-btn-secondary"
                  >
                    预览房间
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="endedSessions.length > 0" class="echo-panel-strong p-4 space-y-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-slate-900">已结束（可查看）</div>
              <div class="text-xs text-slate-500">count: {{ endedSessions.length }}</div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div
                v-for="session in endedSessions"
                :key="`ended-${session.id}`"
                class="rounded-xl border p-4 space-y-3 bg-white/85 border-slate-200"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs uppercase text-slate-500">Session {{ session.id }}</div>
                    <div class="font-semibold text-slate-900">{{ topicTitle(sessionTopicId(session)) }}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-xs uppercase text-slate-500">Status</div>
                    <div class="text-sm font-semibold text-slate-900">{{ session.status }}</div>
                  </div>
                </div>
                <div class="text-xs text-slate-500">
                  开始: {{ formatDateTime(session.scheduledStartAt) }} |
                  结束: {{ formatDateTime(session.endAt) }}
                </div>
                <button
                  @click="enterRoom(session.id)"
                  class="echo-btn-secondary"
                >
                  查看房间
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from '../components/Sidebar.vue';
import {
  classifyLobbySessionLane,
  filterDebateSessions,
  normalizeLobbyLane,
  normalizeSessionTopicId,
  splitLobbySessionsByLane,
} from '../debate-lobby-utils.ts';

function routeQuerySnapshot(query = {}) {
  return [
    String(query.topic || ''),
    String(query.q || ''),
    String(query.status || ''),
    String(query.lane || ''),
    String(query.joinable || ''),
  ].join('|');
}

function normalizeStatusFilter(status) {
  const value = String(status || '').trim().toLowerCase();
  const allowed = new Set([
    'all',
    'joinable',
    'live',
    'upcoming',
    'open',
    'running',
    'ended',
  ]);
  if (!allowed.has(value)) {
    return 'all';
  }
  return value;
}

export default {
  components: {
    Sidebar,
  },
  watch: {
    '$route.query': {
      deep: true,
      handler() {
        this.applyRouteFilters();
      },
    },
    selectedTopicId() {
      this.syncRouteQuery();
    },
    statusFilter() {
      this.syncRouteQuery();
    },
    laneFilter() {
      this.syncRouteQuery();
    },
    keyword() {
      this.syncRouteQuery();
    },
    joinableOnly() {
      this.syncRouteQuery();
    },
  },
  data() {
    return {
      topics: [],
      sessions: [],
      selectedTopicId: '',
      statusFilter: 'all',
      laneFilter: 'all',
      joinableOnly: false,
      keyword: '',
      loading: false,
      errorText: '',
      guardNoticeText: '',
    };
  },
  computed: {
    filteredSessions() {
      return filterDebateSessions(this.sessions, {
        selectedTopicId: this.selectedTopicId,
        statusFilter: this.statusFilter,
        laneFilter: this.laneFilter,
        joinableOnly: this.joinableOnly,
        keyword: this.keyword,
        topicTitleById: (topicId) => this.topicTitle(topicId),
      });
    },
    laneBuckets() {
      return splitLobbySessionsByLane(this.filteredSessions);
    },
    liveSessions() {
      return this.laneBuckets.live;
    },
    upcomingSessions() {
      return this.laneBuckets.upcoming;
    },
    endedSessions() {
      return this.laneBuckets.ended;
    },
    hasAnyVisibleSessions() {
      return this.filteredSessions.length > 0;
    },
    searchActionSessions() {
      if (!this.keyword) {
        return [];
      }
      return this.filteredSessions.slice(0, 8);
    },
  },
  methods: {
    applyRouteFilters() {
      const routeQuery = this.$route?.query || {};
      this.selectedTopicId = String(routeQuery.topic || '').trim();
      this.keyword = String(routeQuery.q || '').trim();
      this.statusFilter = normalizeStatusFilter(routeQuery.status);
      this.laneFilter = normalizeLobbyLane(routeQuery.lane);
      const rawJoinable = String(routeQuery.joinable || '').trim().toLowerCase();
      this.joinableOnly = rawJoinable === '1' || rawJoinable === 'true' || rawJoinable === 'yes';
      const rawNoOpsAccess = String(routeQuery.noOpsAccess || '').trim().toLowerCase();
      if (rawNoOpsAccess === '1' || rawNoOpsAccess === 'true' || rawNoOpsAccess === 'yes') {
        this.guardNoticeText = '当前账号没有 Debate Ops 权限，已为你跳转到辩论大厅。';
      }
    },
    buildRouteQuery() {
      const query = {};
      if (this.selectedTopicId) {
        query.topic = this.selectedTopicId;
      }
      if (this.keyword) {
        query.q = this.keyword;
      }
      if (this.statusFilter && this.statusFilter !== 'all') {
        query.status = normalizeStatusFilter(this.statusFilter);
      }
      if (this.laneFilter && this.laneFilter !== 'all') {
        query.lane = this.laneFilter;
      }
      if (this.joinableOnly) {
        query.joinable = '1';
      }
      return query;
    },
    async syncRouteQuery() {
      const nextQuery = this.buildRouteQuery();
      const currentSnapshot = routeQuerySnapshot(this.$route?.query || {});
      const nextSnapshot = routeQuerySnapshot(nextQuery);
      if (currentSnapshot === nextSnapshot) {
        return;
      }
      await this.$router.replace({ path: this.$route.path, query: nextQuery });
    },
    getSessionLane(session) {
      return classifyLobbySessionLane(session);
    },
    sessionTopicId(session) {
      return normalizeSessionTopicId(session);
    },
    topicTitle(topicId) {
      if (!Number.isFinite(Number(topicId))) {
        return '未知辩题';
      }
      const topic = this.topics.find((item) => item.id === topicId);
      return topic?.title || `topic#${topicId}`;
    },
    formatDateTime(value) {
      if (!value) {
        return '-';
      }
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString();
    },
    async refreshLobby() {
      this.loading = true;
      this.errorText = '';
      try {
        const [topics, sessions] = await Promise.all([
          this.$store.dispatch('listDebateTopics', { activeOnly: true, limit: 100 }),
          this.$store.dispatch('listDebateSessions', { limit: 100 }),
        ]);
        this.topics = topics;
        this.sessions = sessions;
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '刷新失败';
      } finally {
        this.loading = false;
      }
    },
    async joinAndEnter(session, side) {
      if (!session?.joinable) {
        this.errorText = '当前场次暂不可加入，请选择待开启且可加入的场次。';
        return;
      }
      this.loading = true;
      this.errorText = '';
      try {
        await this.$store.dispatch('joinDebateSession', {
          sessionId: session.id,
          side,
        });
        await this.enterRoom(session.id);
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '加入辩论失败';
      } finally {
        this.loading = false;
      }
    },
    async enterRoom(sessionId) {
      await this.$router.push(`/debate/sessions/${sessionId}`);
    },
  },
  async mounted() {
    this.applyRouteFilters();
    await this.refreshLobby();
  },
};
</script>
