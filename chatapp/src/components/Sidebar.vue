<template>
  <div class="w-64 bg-gray-800 text-white flex flex-col h-screen p-4 text-sm">
    <div class="flex items-center justify-between mb-6">
      <div class="font-bold text-base truncate cursor-pointer" @click="toggleDropdown">
        <span>{{ displayName }}</span>
        <button class="text-gray-400 ml-1">&nbsp;▼</button>
      </div>
      <div v-if="dropdownVisible" class="absolute top-12 left-0 w-48 bg-gray-800 border border-gray-700 rounded-md shadow-lg z-10">
        <ul class="py-1">
          <li @click="logout" class="px-4 py-2 hover:bg-gray-700 cursor-pointer">Logout</li>
          <!-- Add more dropdown items here as needed -->
        </ul>
      </div>
      <button @click="addChannel" class="text-gray-400 text-xl hover:text-white">+</button>
    </div>

    <div class="mb-6">
      <h2 class="text-xs uppercase text-gray-400 mb-2">Navigation</h2>
      <ul>
        <li
          @click="goRoute('/home')"
          :class="['px-2 py-1 rounded cursor-pointer mb-1', { 'bg-blue-600': isRouteActive('/home') }]"
        >
          Home
        </li>
        <li
          @click="goRoute('/chat')"
          :class="['px-2 py-1 rounded cursor-pointer mb-1', { 'bg-blue-600': isRouteActive('/chat') }]"
        >
          Chat
        </li>
        <li
          @click="goRoute('/judge-report')"
          :class="['px-2 py-1 rounded cursor-pointer', { 'bg-blue-600': isRouteActive('/judge-report') }]"
        >
          AI Judge
        </li>
        <li
          @click="goRoute('/debate')"
          :class="['px-2 py-1 rounded cursor-pointer mt-1', { 'bg-blue-600': isRouteActive('/debate') }]"
        >
          Debate
        </li>
        <li
          v-if="canAccessDebateOps"
          @click="goRoute('/debate/ops')"
          :class="['px-2 py-1 rounded cursor-pointer mt-1', { 'bg-blue-600': isRouteActive('/debate/ops') }]"
        >
          Debate Ops
        </li>
        <li
          @click="goRoute('/wallet')"
          :class="['px-2 py-1 rounded cursor-pointer mt-1', { 'bg-blue-600': isRouteActive('/wallet') }]"
        >
          Wallet
        </li>
        <li
          @click="goRoute('/me')"
          :class="['px-2 py-1 rounded cursor-pointer mt-1', { 'bg-blue-600': isRouteActive('/me') }]"
        >
          Me
        </li>
        <li
          @click="goRoute('/notifications')"
          :class="['px-2 py-1 rounded cursor-pointer mt-1', { 'bg-blue-600': isRouteActive('/notifications') }]"
        >
          Notifications
        </li>
      </ul>
    </div>

    <div class="mb-6">
      <h2 class="text-xs uppercase text-gray-400 mb-2">Channels</h2>
      <ul>
        <li v-for="channel in channels" :key="channel.id" @click="selectChannel(channel.id)"
            :class="['px-2 py-1 rounded cursor-pointer', { 'bg-blue-600': channel.id === activeChannelId }]">
          # {{ channel.name }}
        </li>
      </ul>
    </div>

    <div>
      <h2 class="text-xs uppercase text-gray-400 mb-2">Direct Messages</h2>
      <ul>
        <li v-for="channel in singleChannels" :key="channel.id" @click="selectChannel(channel.id)"
            :class="['flex items-center px-2 py-1 rounded cursor-pointer', { 'bg-blue-600': channel.id === activeChannelId }]">
          <img :src="`https://ui-avatars.com/api/?name=${channel.recipient.fullname.replace(' ', '+')}`"
               class="w-6 h-6 rounded-full mr-2" alt="Avatar" />
          {{ channel.recipient.fullname }}
        </li>
      </ul>
    </div>
  </div>
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
