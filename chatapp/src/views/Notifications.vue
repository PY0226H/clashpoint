<template>
  <div class="flex h-screen echo-shell">
    <Sidebar />
    <div class="echo-main">
      <div class="max-w-4xl mx-auto p-6 lg:p-8 space-y-4 echo-fade-in">
        <div class="echo-panel-strong p-5 flex items-start justify-between gap-3">
          <div>
            <div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">Notification Center</div>
            <h1 class="text-2xl font-semibold text-slate-900 mt-1">通知中心</h1>
            <p class="text-sm text-slate-600 mt-1">聚合关键赛事通知：判决生成、平局投票决议。</p>
          </div>
          <button
            @click="goTo('/home')"
            class="echo-btn-secondary"
          >
            返回首页
          </button>
        </div>

        <div class="echo-panel p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="text-sm font-semibold text-slate-900">通知列表</div>
            <div class="text-xs text-slate-500">unread: {{ notificationCount }}</div>
          </div>

          <div v-if="notificationCount === 0" class="text-sm text-slate-600">
            当前暂无关键通知，参与一场辩论后会在此展示最新状态。
          </div>

          <div v-else class="space-y-2">
            <button
              v-for="item in notificationItems"
              :key="item.key"
              @click="openNotification(item)"
              class="w-full text-left border rounded-xl p-3 bg-white/85 border-slate-200 hover:border-blue-300 transition"
            >
              <div class="flex items-center justify-between gap-3">
                <div class="text-sm font-semibold text-slate-900">{{ item.title }}</div>
                <div class="text-xs text-slate-500">{{ formatDateTime(item.createdAtMs) }}</div>
              </div>
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
  buildNotificationCenterItems,
  countNotificationCenterItems,
} from '../notification-center-utils';

export default {
  components: {
    Sidebar,
  },
  computed: {
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
    formatDateTime(value) {
      if (!value) {
        return '-';
      }
      const date = new Date(value);
      return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString();
    },
    async goTo(path) {
      if (this.$route.path === path) {
        return;
      }
      await this.$router.push(path);
    },
    async openNotification(item) {
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
};
</script>
