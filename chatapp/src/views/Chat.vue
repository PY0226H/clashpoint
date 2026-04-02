<template>
  <div class="flex h-screen echo-shell">
    <Sidebar />
    <div class="echo-main">
      <div class="max-w-7xl mx-auto p-6 lg:p-8 h-full flex flex-col gap-4 echo-fade-in">
        <div class="echo-panel-strong relative overflow-hidden p-5 lg:p-6">
          <div class="absolute inset-0 bg-gradient-to-br from-indigo-100/70 via-white to-sky-100/70"></div>
          <div class="absolute -left-20 -top-20 w-64 h-64 rounded-full bg-indigo-200/35 blur-3xl"></div>
          <div class="absolute -right-20 -bottom-20 w-64 h-64 rounded-full bg-sky-200/35 blur-3xl"></div>
          <div class="relative flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div class="space-y-2 max-w-3xl">
              <div class="text-[11px] uppercase tracking-[0.24em] text-slate-500">Chat Workspace</div>
              <h1 class="text-2xl lg:text-3xl font-semibold text-slate-900">会话工作台</h1>
              <p class="text-sm text-slate-700">
                统一管理群聊与单聊消息流，保持会话沟通、辩论协作与通知触达的连续性。
              </p>
            </div>
            <div class="grid grid-cols-2 gap-2 text-xs lg:w-[320px]">
              <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                群聊 {{ groupChannels.length }}
              </div>
              <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                单聊 {{ singleChannels.length }}
              </div>
              <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                当前 {{ activeChannelLabel }}
              </div>
              <div class="rounded-xl border border-slate-200 bg-white/85 px-3 py-2 text-slate-700">
                消息 {{ activeMessages.length }}
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 xl:grid-cols-4 gap-4 flex-1 min-h-0">
          <section class="echo-panel-strong flex flex-col min-h-0 xl:col-span-3">
            <div class="px-4 py-3 border-b border-slate-200/80 flex items-center justify-between gap-3">
              <div>
                <div class="text-xs uppercase tracking-[0.2em] text-slate-500">消息流</div>
                <div class="text-sm font-semibold text-slate-900 mt-1">{{ activeChannelTitle }}</div>
              </div>
              <div class="text-xs text-slate-600">
                频道 {{ groupChannels.length + singleChannels.length }} · 当前会话消息 {{ activeMessages.length }}
              </div>
            </div>
            <MessageList class="flex-1 min-h-0 overflow-y-auto" />
            <div class="border-t border-slate-200/80 bg-white/75">
              <MessageSend />
            </div>
          </section>

          <aside class="echo-panel p-4 space-y-3 xl:col-span-1">
            <div class="text-xs uppercase tracking-[0.2em] text-slate-500">工作区动作</div>
            <div class="text-sm text-slate-700">
              你可以从会话直接切换到辩论大厅、裁判报告与通知中心，减少跨页上下文损耗。
            </div>
            <div class="flex flex-wrap gap-2">
              <button type="button" class="echo-btn-secondary text-xs px-3 py-1.5" @click="goTo('/debate')">
                去辩论大厅
              </button>
              <button type="button" class="echo-btn-secondary text-xs px-3 py-1.5" @click="goTo('/judge-report')">
                去裁判报告
              </button>
              <button type="button" class="echo-btn-secondary text-xs px-3 py-1.5" @click="goTo('/notifications')">
                去通知中心
              </button>
            </div>
            <div class="pt-2 border-t border-slate-200/80 text-xs text-slate-600 space-y-1">
              <div>提示 1：消息发送前请确认侧边栏已选中会话。</div>
              <div>提示 2：上传图片后可直接在输入区预览再发送。</div>
              <div>提示 3：会话切换会自动刷新当前频道消息。</div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from '../components/Sidebar.vue';
import MessageList from '../components/MessageList.vue';
import MessageSend from '../components/MessageSend.vue';

export default {
  components: {
    Sidebar,
    MessageList,
    MessageSend,
  },
  computed: {
    groupChannels() {
      return this.$store.getters.getChannels || [];
    },
    singleChannels() {
      return this.$store.getters.getSingChannels || [];
    },
    activeChannel() {
      return this.$store.state.activeChannel || null;
    },
    activeMessages() {
      return this.$store.getters.getMessagesForActiveChannel || [];
    },
    activeChannelLabel() {
      if (!this.activeChannel) {
        return '未选择';
      }
      if (this.activeChannel.type === 'single') {
        const matched = this.singleChannels.find((item) => item.id === this.activeChannel.id);
        return matched?.recipient?.fullname || `DM #${this.activeChannel.id}`;
      }
      return this.activeChannel.name || `频道 #${this.activeChannel.id}`;
    },
    activeChannelTitle() {
      if (!this.activeChannel) {
        return '请先在左侧选择会话';
      }
      if (this.activeChannel.type === 'single') {
        return `单聊 · ${this.activeChannelLabel}`;
      }
      return `群聊 · ${this.activeChannelLabel}`;
    },
  },
  methods: {
    async goTo(path) {
      if (this.$route.path === path) {
        return;
      }
      await this.$router.push(path);
    },
  },
};
</script>
