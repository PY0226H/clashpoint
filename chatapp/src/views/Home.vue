<template>
  <div class="flex h-screen echo-shell">
    <Sidebar />
    <div class="echo-main">
      <div class="max-w-6xl mx-auto p-6 lg:p-8 space-y-5 echo-fade-in">
        <div class="echo-panel-strong p-6 flex flex-wrap items-start justify-between gap-4">
          <div class="space-y-2">
            <div class="text-[11px] uppercase tracking-[0.28em] text-slate-500">Mac 控制台</div>
            <h1 class="text-3xl font-semibold text-slate-900">EchoIsle 首页工作台</h1>
            <p class="text-sm text-slate-600 max-w-2xl">
              四入口保持与你 PRD 一致：会话、辩论广场、搜索、个人中心。
            </p>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <div class="px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-xs text-slate-600">
              群聊 {{ groupChannels.length }} · 单聊 {{ singleChannels.length }}
            </div>
            <div class="px-3 py-2 rounded-xl border border-slate-200 bg-white/90 text-xs text-slate-600">
              场次 {{ debateStats.total }} · 进行中 {{ debateStats.live }}
            </div>
            <button
              @click="refreshHome"
              :disabled="loading"
              class="echo-btn-primary disabled:opacity-60"
            >
              {{ loading ? '刷新中...' : '刷新首页' }}
            </button>
          </div>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 border border-red-200 rounded-xl p-3 text-sm">
          {{ errorText }}
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button
            @click="goTo('/chat')"
            class="echo-panel p-5 text-left hover:-translate-y-0.5 transition"
          >
            <div class="text-xs uppercase tracking-[0.2em] text-slate-500">入口 1</div>
            <div class="text-lg font-semibold text-slate-900 mt-1">会话</div>
            <div class="text-sm text-slate-600 mt-2">
              群聊 {{ groupChannels.length }} · 单聊 {{ singleChannels.length }}
            </div>
          </button>

          <button
            @click="goTo('/debate')"
            class="echo-panel p-5 text-left hover:-translate-y-0.5 transition"
          >
            <div class="text-xs uppercase tracking-[0.2em] text-slate-500">入口 2</div>
            <div class="text-lg font-semibold text-slate-900 mt-1">辩论广场</div>
            <div class="text-sm text-slate-600 mt-2">
              场次 {{ debateStats.total }} · 进行中 {{ debateStats.live }} · 可加入 {{ debateStats.joinable }}
            </div>
          </button>

          <div class="echo-panel p-5">
            <div class="text-xs uppercase tracking-[0.2em] text-slate-500">入口 3</div>
            <div class="text-lg font-semibold text-slate-900 mt-1">搜索</div>
            <div class="text-sm text-slate-600 mt-2 mb-3">
              检索会话/辩题/场次并一键跳转。
            </div>
            <input
              v-model.trim="searchQuery"
              type="text"
              placeholder="输入关键词，例如：平衡 / session 12 / General"
              class="echo-field"
            />
          </div>

          <div class="echo-panel p-5 text-left">
            <div class="text-xs uppercase tracking-[0.2em] text-slate-500">入口 4</div>
            <div class="text-lg font-semibold text-slate-900 mt-1">个人中心</div>
            <div class="text-sm text-slate-600 mt-2">
              当前余额 {{ walletBalance }} · 通知 {{ notificationCount }}
            </div>
            <div class="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                class="echo-btn-secondary text-xs px-3 py-1.5"
                @click="goTo('/me')"
              >
                个人资料
              </button>
              <button
                type="button"
                class="echo-btn-secondary text-xs px-3 py-1.5"
                @click="goTo('/notifications')"
              >
                通知中心
              </button>
              <button
                type="button"
                class="echo-btn-secondary text-xs px-3 py-1.5"
                @click="goTo('/wallet')"
              >
                去充值
              </button>
            </div>
          </div>
        </div>

        <div class="echo-panel-strong p-4 space-y-2">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-slate-900">搜索结果</div>
            <div class="text-xs text-slate-500">items: {{ searchResults.length }}</div>
          </div>
          <div v-if="searchResults.length === 0" class="text-sm text-slate-600">
            暂无匹配结果，请尝试其它关键词。
          </div>
          <div v-else class="space-y-2">
            <button
              v-for="item in searchResults"
              :key="item.key"
              @click="openSearchItem(item)"
              class="w-full text-left border rounded-xl p-3 bg-white/85 border-slate-200 hover:border-blue-300 transition"
            >
              <div class="text-sm font-semibold text-slate-900">{{ item.title }}</div>
              <div class="text-xs text-slate-600 mt-1">{{ item.subtitle }}</div>
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from '../components/Sidebar.vue';
import {
  buildHomeSearchIndex,
  filterHomeSearchItems,
  summarizeDebateSessionStats,
} from '../home-utils';
import {
  buildNotificationCenterItems,
  countNotificationCenterItems,
} from '../notification-center-utils';

export default {
  components: {
    Sidebar,
  },
  data() {
    return {
      loading: false,
      errorText: '',
      walletBalance: 0,
      topics: [],
      sessions: [],
      searchQuery: '',
    };
  },
  computed: {
    groupChannels() {
      return this.$store.getters.getChannels || [];
    },
    singleChannels() {
      return this.$store.getters.getSingChannels || [];
    },
    debateStats() {
      return summarizeDebateSessionStats(this.sessions);
    },
    searchIndex() {
      const channels = [...this.groupChannels, ...this.singleChannels];
      return buildHomeSearchIndex({
        channels,
        topics: this.topics,
        sessions: this.sessions,
        topicTitleById: (topicId) => {
          const topic = this.topics.find((item) => item.id === topicId);
          return topic?.title || '';
        },
      });
    },
    searchResults() {
      return filterHomeSearchItems(this.searchIndex, this.searchQuery, { limit: 12 });
    },
    notificationItems() {
      return buildNotificationCenterItems({
        latestJudgeReportEvent: this.$store.getters.getLatestJudgeReportEvent,
        latestDrawVoteResolvedEvent: this.$store.getters.getLatestDrawVoteResolvedEvent,
      });
    },
    notificationCount() {
      return countNotificationCenterItems(this.notificationItems);
    },
  },
  methods: {
    async refreshHome() {
      this.loading = true;
      this.errorText = '';
      try {
        const [topics, sessions, wallet] = await Promise.all([
          this.$store.dispatch('listDebateTopics', { activeOnly: true, limit: 100 }),
          this.$store.dispatch('listDebateSessions', { limit: 100 }),
          this.$store.dispatch('fetchWalletBalance'),
        ]);
        this.topics = topics || [];
        this.sessions = sessions || [];
        this.walletBalance = Number(wallet?.balance || 0);
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '刷新首页失败';
      } finally {
        this.loading = false;
      }
    },
    async goTo(path) {
      if (this.$route.path === path) {
        return;
      }
      await this.$router.push(path);
    },
    async openSearchItem(item) {
      if (!item?.path) {
        return;
      }
      if (item.query) {
        await this.$router.push({ path: item.path, query: item.query });
        return;
      }
      await this.$router.push(item.path);
    },
  },
  async mounted() {
    await this.refreshHome();
  },
};
</script>
