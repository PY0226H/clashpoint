<template>
  <div class="flex h-screen echo-shell">
    <Sidebar />
    <div class="echo-main">
      <div class="max-w-6xl mx-auto p-6 lg:p-8 space-y-5 echo-fade-in">
        <div class="echo-panel-strong relative overflow-hidden p-6 lg:p-7">
          <div class="absolute inset-0 bg-gradient-to-br from-indigo-100/75 via-white to-sky-100/75"></div>
          <div class="absolute -left-20 -top-20 h-64 w-64 rounded-full bg-indigo-200/40 blur-3xl"></div>
          <div class="absolute -right-20 -bottom-20 h-64 w-64 rounded-full bg-sky-200/40 blur-3xl"></div>
          <div class="relative flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div class="max-w-3xl space-y-2">
              <div class="text-[11px] uppercase tracking-[0.28em] text-slate-500">Mac 控制台</div>
              <h1 class="text-3xl font-semibold text-slate-900">EchoIsle 首页工作台</h1>
              <p class="text-sm text-slate-700">
                四入口保持与你 PRD 一致：会话、辩论广场、搜索、个人中心；首屏聚焦可操作与状态总览。
              </p>
              <div class="text-xs text-slate-600">
                当前检索项 {{ searchResults.length }} · 可加入场次 {{ debateStats.joinable }} · 通知 {{ notificationCount }}
              </div>
            </div>
            <div class="w-full lg:w-[360px] space-y-3">
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                  会话 {{ groupChannels.length + singleChannels.length }}
                </div>
                <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                  进行中 {{ debateStats.live }}
                </div>
                <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                  钱包 {{ walletBalance }}
                </div>
                <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                  待处理通知 {{ notificationCount }}
                </div>
              </div>
              <button
                @click="refreshHome"
                :disabled="loading"
                class="echo-btn-primary w-full disabled:opacity-60"
              >
                {{ loading ? '刷新中...' : '刷新首页' }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="errorText" class="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {{ errorText }}
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <div class="echo-panel-strong p-5 space-y-3 xl:col-span-2">
            <div class="flex items-center justify-between gap-2">
              <div>
                <div class="text-xs uppercase tracking-[0.2em] text-slate-500">四入口调度台</div>
                <div class="text-sm text-slate-700 mt-1">保持首页四入口路径稳定，降低操作跳转成本。</div>
              </div>
              <div class="text-xs text-slate-500">会话 {{ groupChannels.length + singleChannels.length }} · 场次 {{ debateStats.total }}</div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <button
                @click="goTo('/chat')"
                class="echo-panel p-4 text-left hover:-translate-y-0.5 transition"
              >
                <div class="text-[11px] uppercase tracking-[0.2em] text-slate-500">入口 1</div>
                <div class="text-lg font-semibold text-slate-900 mt-1">会话</div>
                <div class="text-sm text-slate-600 mt-1">群聊 {{ groupChannels.length }} · 单聊 {{ singleChannels.length }}</div>
              </button>

              <button
                @click="goTo('/debate')"
                class="echo-panel p-4 text-left hover:-translate-y-0.5 transition"
              >
                <div class="text-[11px] uppercase tracking-[0.2em] text-slate-500">入口 2</div>
                <div class="text-lg font-semibold text-slate-900 mt-1">辩论广场</div>
                <div class="text-sm text-slate-600 mt-1">
                  场次 {{ debateStats.total }} · 进行中 {{ debateStats.live }} · 可加入 {{ debateStats.joinable }}
                </div>
              </button>

              <div class="echo-panel p-4 text-left">
                <div class="text-[11px] uppercase tracking-[0.2em] text-slate-500">入口 3</div>
                <div class="text-lg font-semibold text-slate-900 mt-1">搜索</div>
                <div class="text-sm text-slate-600 mt-1">检索会话/辩题/场次并从下方结果区一键跳转。</div>
              </div>

              <button
                type="button"
                @click="goTo('/me')"
                class="echo-panel p-4 text-left hover:-translate-y-0.5 transition"
              >
                <div class="text-[11px] uppercase tracking-[0.2em] text-slate-500">入口 4</div>
                <div class="text-lg font-semibold text-slate-900 mt-1">个人中心</div>
                <div class="text-sm text-slate-600 mt-1">当前余额 {{ walletBalance }} · 通知 {{ notificationCount }}</div>
              </button>
            </div>
          </div>

          <div class="space-y-4">
            <div class="echo-panel p-5 space-y-3">
              <div class="text-xs uppercase tracking-[0.2em] text-slate-500">检索工作区</div>
              <div class="text-sm font-semibold text-slate-900">输入关键词快速定位目标场次</div>
              <input
                v-model.trim="searchQuery"
                type="text"
                placeholder="输入关键词，例如：平衡 / session 12 / General"
                class="echo-field"
              />
              <div class="text-xs text-slate-600">
                当前匹配 {{ searchResults.length }} 条，可在下方“搜索结果”直接跳转。
              </div>
            </div>

            <div class="echo-panel p-5 space-y-3 text-left">
              <div class="text-xs uppercase tracking-[0.2em] text-slate-500">个人中心快捷操作</div>
              <div class="text-sm text-slate-700">围绕账号、通知、充值形成闭环操作路径。</div>
              <div class="flex flex-wrap gap-2">
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

<script lang="ts">
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
      const buildHomeSearchIndexSafe = buildHomeSearchIndex as unknown as (payload: {
        channels: unknown[];
        topics: unknown[];
        sessions: unknown[];
        topicTitleById: (topicId: unknown) => string;
      }) => unknown[];
      return buildHomeSearchIndexSafe({
        channels,
        topics: this.topics,
        sessions: this.sessions,
        topicTitleById: (topicId: unknown) => {
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
