<template>
  <div class="flex h-screen">
    <Sidebar />
    <div class="flex-1 overflow-y-auto bg-gray-50">
      <div class="max-w-6xl mx-auto p-6 space-y-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">Debate Lobby</h1>
            <p class="text-sm text-gray-600 mt-1">按“进行中/待开启”分流：进行中可观战，待开启可选阵营加入。</p>
          </div>
          <button
            @click="refreshLobby"
            :disabled="loading"
            class="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 border border-red-200 rounded p-3 text-sm">
          {{ errorText }}
        </div>

        <div class="bg-white border rounded-lg p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
          <div>
            <div class="text-xs uppercase text-gray-500 mb-1">Topic</div>
            <select
              v-model="selectedTopicId"
              class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">全部辩题</option>
              <option v-for="topic in topics" :key="topic.id" :value="String(topic.id)">
                {{ topic.title }}
              </option>
            </select>
          </div>
          <div>
            <div class="text-xs uppercase text-gray-500 mb-1">Status</div>
            <select
              v-model="statusFilter"
              class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
            <div class="text-xs uppercase text-gray-500 mb-1">Keyword</div>
            <input
              v-model.trim="keyword"
              class="w-full border rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="按辩题关键词筛选"
            />
          </div>
          <label class="inline-flex items-center gap-2 text-xs text-gray-700 self-end">
            <input v-model="joinableOnly" type="checkbox" class="rounded border-gray-300" />
            仅可加入
          </label>
          <div class="text-xs text-gray-500 self-end text-right">
            sessions: {{ filteredSessions.length }} / {{ sessions.length }}
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div class="bg-white border rounded-lg p-3">
            <div class="text-xs uppercase text-gray-500">进行中（观战）</div>
            <div class="text-xl font-semibold text-gray-900 mt-1">{{ liveSessions.length }}</div>
          </div>
          <div class="bg-white border rounded-lg p-3">
            <div class="text-xs uppercase text-gray-500">待开启（可加入）</div>
            <div class="text-xl font-semibold text-gray-900 mt-1">{{ upcomingSessions.length }}</div>
          </div>
          <div class="bg-white border rounded-lg p-3">
            <div class="text-xs uppercase text-gray-500">已结束</div>
            <div class="text-xl font-semibold text-gray-900 mt-1">{{ endedSessions.length }}</div>
          </div>
        </div>

        <div v-if="!hasAnyVisibleSessions" class="bg-white border rounded-lg p-5 text-sm text-gray-600">
          当前筛选下没有可用场次。
        </div>

        <div v-else class="space-y-4">
          <div v-if="liveSessions.length > 0" class="bg-white border rounded-lg p-4 space-y-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-gray-900">进行中（可观战）</div>
              <div class="text-xs text-gray-500">count: {{ liveSessions.length }}</div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div
                v-for="session in liveSessions"
                :key="`live-${session.id}`"
                class="rounded-lg border p-4 space-y-3 bg-gray-50"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs uppercase text-gray-500">Session {{ session.id }}</div>
                    <div class="font-semibold text-gray-900">{{ topicTitle(sessionTopicId(session)) }}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-xs uppercase text-gray-500">Status</div>
                    <div class="text-sm font-semibold text-gray-900">{{ session.status }}</div>
                  </div>
                </div>

                <div class="text-xs text-gray-500">
                  开始: {{ formatDateTime(session.scheduledStartAt) }} |
                  结束: {{ formatDateTime(session.endAt) }}
                </div>

                <div class="text-sm text-gray-700 flex gap-3">
                  <span>Pro: <strong>{{ session.proCount }}</strong></span>
                  <span>Con: <strong>{{ session.conCount }}</strong></span>
                  <span>Hot: <strong>{{ session.hotScore }}</strong></span>
                </div>

                <div class="flex flex-wrap gap-2">
                  <button
                    @click="enterRoom(session.id)"
                    class="px-3 py-2 rounded border border-gray-300 text-gray-800 text-sm bg-white hover:bg-gray-100"
                  >
                    观战房间
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="upcomingSessions.length > 0" class="bg-white border rounded-lg p-4 space-y-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-gray-900">待开启（可加入）</div>
              <div class="text-xs text-gray-500">count: {{ upcomingSessions.length }}</div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div
                v-for="session in upcomingSessions"
                :key="`upcoming-${session.id}`"
                class="rounded-lg border p-4 space-y-3 bg-gray-50"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs uppercase text-gray-500">Session {{ session.id }}</div>
                    <div class="font-semibold text-gray-900">{{ topicTitle(sessionTopicId(session)) }}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-xs uppercase text-gray-500">Status</div>
                    <div class="text-sm font-semibold text-gray-900">{{ session.status }}</div>
                  </div>
                </div>

                <div class="text-xs text-gray-500">
                  开始: {{ formatDateTime(session.scheduledStartAt) }} |
                  结束: {{ formatDateTime(session.endAt) }}
                </div>

                <div class="text-sm text-gray-700 flex gap-3">
                  <span>Pro: <strong>{{ session.proCount }}</strong></span>
                  <span>Con: <strong>{{ session.conCount }}</strong></span>
                  <span>Hot: <strong>{{ session.hotScore }}</strong></span>
                </div>

                <div class="flex flex-wrap gap-2">
                  <button
                    @click="joinAndEnter(session, 'pro')"
                    :disabled="loading || !session.joinable"
                    class="px-3 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
                  >
                    加入正方
                  </button>
                  <button
                    @click="joinAndEnter(session, 'con')"
                    :disabled="loading || !session.joinable"
                    class="px-3 py-2 rounded bg-orange-600 text-white text-sm disabled:opacity-50"
                  >
                    加入反方
                  </button>
                  <button
                    @click="enterRoom(session.id)"
                    class="px-3 py-2 rounded border border-gray-300 text-gray-800 text-sm bg-white hover:bg-gray-100"
                  >
                    预览房间
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-if="endedSessions.length > 0" class="bg-white border rounded-lg p-4 space-y-3">
            <div class="flex items-center justify-between">
              <div class="text-sm font-semibold text-gray-900">已结束（可查看）</div>
              <div class="text-xs text-gray-500">count: {{ endedSessions.length }}</div>
            </div>
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div
                v-for="session in endedSessions"
                :key="`ended-${session.id}`"
                class="rounded-lg border p-4 space-y-3 bg-gray-50"
              >
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <div class="text-xs uppercase text-gray-500">Session {{ session.id }}</div>
                    <div class="font-semibold text-gray-900">{{ topicTitle(sessionTopicId(session)) }}</div>
                  </div>
                  <div class="text-right">
                    <div class="text-xs uppercase text-gray-500">Status</div>
                    <div class="text-sm font-semibold text-gray-900">{{ session.status }}</div>
                  </div>
                </div>
                <div class="text-xs text-gray-500">
                  开始: {{ formatDateTime(session.scheduledStartAt) }} |
                  结束: {{ formatDateTime(session.endAt) }}
                </div>
                <button
                  @click="enterRoom(session.id)"
                  class="px-3 py-2 rounded border border-gray-300 text-gray-800 text-sm bg-white hover:bg-gray-100"
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
  filterDebateSessions,
  normalizeSessionTopicId,
  splitLobbySessionsByLane,
} from '../debate-lobby-utils';

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
  },
  data() {
    return {
      topics: [],
      sessions: [],
      selectedTopicId: '',
      statusFilter: 'all',
      joinableOnly: false,
      keyword: '',
      loading: false,
      errorText: '',
    };
  },
  computed: {
    filteredSessions() {
      return filterDebateSessions(this.sessions, {
        selectedTopicId: this.selectedTopicId,
        statusFilter: this.statusFilter,
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
  },
  methods: {
    applyRouteFilters() {
      const routeQuery = this.$route?.query || {};
      if (routeQuery.topic != null) {
        this.selectedTopicId = String(routeQuery.topic || '').trim();
      }
      if (routeQuery.q != null) {
        this.keyword = String(routeQuery.q || '').trim();
      }
      if (routeQuery.status != null) {
        this.statusFilter = String(routeQuery.status || '').trim() || this.statusFilter;
      }
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
