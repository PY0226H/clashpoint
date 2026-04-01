<template>
  <aside class="w-72 bg-slate-950 text-slate-100 flex flex-col h-screen px-4 py-5 border-r border-slate-800/90 shadow-[18px_0_34px_rgba(2,6,23,0.35)] text-sm">
    <div class="flex items-center justify-between mb-6 relative">
      <button type="button" class="min-w-0 text-left" @click="toggleDropdown">
        <div class="text-[11px] uppercase tracking-[0.24em] text-slate-400">EchoIsle</div>
        <div class="font-semibold text-base truncate mt-1">{{ displayName }}</div>
      </button>
      <button
        type="button"
        @click="addChannel"
        class="w-8 h-8 rounded-full border border-slate-700 text-slate-300 text-lg hover:text-white hover:border-slate-500 transition"
      >
        +
      </button>
      <div
        v-if="dropdownVisible"
        class="absolute top-14 left-0 w-48 bg-slate-900 border border-slate-700/80 rounded-lg shadow-lg z-20"
      >
        <ul class="py-1">
          <li @click="logout" class="px-4 py-2 hover:bg-slate-800 cursor-pointer">Logout</li>
        </ul>
      </div>
    </div>

    <div class="mb-6">
      <h2 class="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-2">Workspace</h2>
      <ul class="space-y-1">
        <li
          @click="goRoute('/home')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/home')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          总览 Home
        </li>
        <li
          @click="goRoute('/chat')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/chat')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          会话 Chat
        </li>
        <li
          @click="goRoute('/judge-report')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/judge-report')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          裁判报告
        </li>
        <li
          @click="goRoute('/debate')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/debate')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          辩论大厅
        </li>
        <li
          v-if="canAccessDebateOps"
          @click="goRoute('/debate/ops')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/debate/ops')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          Ops 后台
        </li>
        <li
          @click="goRoute('/wallet')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/wallet')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          钱包
        </li>
        <li
          @click="goRoute('/me')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/me')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          个人中心
        </li>
        <li
          @click="goRoute('/notifications')"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer transition',
            isRouteActive('/notifications')
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          通知
        </li>
      </ul>
    </div>

    <div class="mb-6 min-h-0">
      <h2 class="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-2">Channels</h2>
      <ul class="space-y-1 max-h-40 overflow-y-auto pr-1">
        <li
          v-for="channel in channels"
          :key="channel.id"
          @click="selectChannel(channel.id)"
          :class="[
            'px-3 py-2 rounded-lg cursor-pointer truncate transition',
            channel.id === activeChannelId
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          # {{ channel.name }}
        </li>
      </ul>
    </div>

    <div class="min-h-0 flex-1">
      <h2 class="text-[11px] uppercase tracking-[0.22em] text-slate-500 mb-2">Direct Messages</h2>
      <ul class="space-y-1 max-h-[calc(100vh-490px)] overflow-y-auto pr-1">
        <li
          v-for="channel in singleChannels"
          :key="channel.id"
          @click="selectChannel(channel.id)"
          :class="[
            'flex items-center px-3 py-2 rounded-lg cursor-pointer transition',
            channel.id === activeChannelId
              ? 'bg-blue-600/85 text-white'
              : 'text-slate-300 hover:bg-slate-800 hover:text-white',
          ]"
        >
          <img
            :src="`https://ui-avatars.com/api/?name=${channel.recipient.fullname.replace(' ', '+')}`"
            class="w-6 h-6 rounded-full mr-2 border border-slate-700"
            alt="Avatar"
          />
          {{ channel.recipient.fullname }}
        </li>
      </ul>
    </div>
  </aside>
</template>

<script>
import { pickDefaultPeerUserId } from '../channel-utils';
import { hasAnyOpsPermission, normalizeOpsRbacMe } from '../ops-permission-utils';

export default {
  data() {
    return {
      dropdownVisible: false,
    };
  },
  computed: {
    displayName() {
      return this.$store.getters.getUser?.fullname || 'EchoIsle';
    },
    channels() {
      return this.$store.getters.getChannels;
    },
    activeChannelId() {
      const channel = this.$store.state.activeChannel;
      if (!channel) {
        return null;
      }
      return channel.id;
    },
    singleChannels() {
      return this.$store.getters.getSingChannels;
    },
    canAccessDebateOps() {
      const snapshot = normalizeOpsRbacMe(this.$store.getters.getOpsRbacMe);
      return hasAnyOpsPermission(snapshot);
    },
  },
  methods: {
    async ensureOpsRbacSnapshot() {
      if (!this.$store.state.token) {
        return;
      }
      try {
        await this.$store.dispatch('getOpsRbacMe');
      } catch (error) {
        console.error('Failed to preload ops RBAC snapshot in sidebar:', error);
      }
    },
    toggleDropdown() {
      this.dropdownVisible = !this.dropdownVisible;
    },
    async logout() {
      const from = `/chats/${this.activeChannelId}`;
      const to = '/logout';
      this.$store.dispatch('navigation', { from, to });
      this.$store.dispatch('userLogout');
      this.$store.dispatch('logout');
      await this.$router.push('/login');
    },
    handleOutsideClick(event) {
      if (!this.$el.contains(event.target)) {
        this.dropdownVisible = false;
      }
    },
    async addChannel() {
      const selfId = this.$store.state.user?.id;
      const peerId = pickDefaultPeerUserId(this.$store.state.users, selfId);
      if (!peerId) {
        alert('当前没有其他用户，无法创建频道。请先注册第二个用户后再创建。');
        return;
      }

      const name = `channel-${this.channels.length + 1}`;
      try {
        const channel = await this.$store.dispatch('createChannel', {
          name,
          members: [selfId, peerId],
          public: false,
        });
        this.selectChannel(channel.id);
      } catch (error) {
        console.error('Failed to create channel:', error);
      }
    },
    goRoute(path) {
      if (path === '/debate/ops' && !this.canAccessDebateOps) {
        alert('当前账号没有 Ops 权限');
        return;
      }
      if (this.$route.path !== path) {
        this.$router.push(path);
      }
    },
    isRouteActive(path) {
      if (path === '/debate/ops') {
        return this.$route.path.startsWith('/debate/ops');
      }
      if (path === '/debate') {
        return this.$route.path.startsWith('/debate') && !this.$route.path.startsWith('/debate/ops');
      }
      if (path === '/chat') {
        return this.$route.path === '/chat';
      }
      if (path === '/home') {
        return this.$route.path === '/home';
      }
      if (path === '/notifications') {
        return this.$route.path.startsWith('/notifications');
      }
      if (path === '/me') {
        return this.$route.path.startsWith('/me');
      }
      return this.$route.path === path;
    },
    selectChannel(channelId) {
      const from = `/chats/${this.activeChannelId}`;
      const to = `/chats/${channelId}`;
      this.$store.dispatch('navigation', { from, to });
      this.$store.dispatch('setActiveChannel', channelId);
      if (this.$route.path !== '/chat') {
        this.$router.push('/chat');
      }
    },
  },
  mounted() {
    document.addEventListener('click', this.handleOutsideClick);
    this.ensureOpsRbacSnapshot();
  },
  beforeDestroy() {
    document.removeEventListener('click', this.handleOutsideClick);
  },
};
</script>
