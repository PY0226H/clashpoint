<template>
  <div class="flex-1 overflow-y-auto px-5 py-4" ref="messageContainer">
    <div v-if="messages.length === 0" class="mt-8 text-center text-sm text-slate-500">
      当前会话还没有消息，发送第一条消息开始协作。
    </div>
    <div v-else class="space-y-4">
      <div v-for="message in messages" :key="message.id" class="flex items-start gap-3">
        <img
          :src="`https://ui-avatars.com/api/?name=${getSender(message.senderId).fullname.replace(' ', '+')}`"
          class="w-9 h-9 rounded-full border border-slate-200"
          alt="Avatar"
        />
        <div class="max-w-[82%]">
          <div class="flex items-center gap-2 mb-1">
            <span class="font-semibold text-sm text-slate-900">{{ getSender(message.senderId).fullname }}</span>
            <span class="text-xs text-slate-500">{{ message.formattedCreatedAt }}</span>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white/85 px-3 py-2 text-sm leading-relaxed break-words whitespace-pre-wrap text-slate-800">
            {{ getMessageContent(message) }}
          </div>
          <div v-if="message.files && message.files.length > 0" class="grid grid-cols-3 gap-2 mt-2 max-w-[540px]">
            <div v-for="(file, index) in message.files" :key="index">
              <img
                :src="getFileUrl(file)"
                :class="{
                  'h-28 w-full rounded-xl border border-slate-200 object-cover cursor-pointer': true,
                  'w-auto h-auto': enlargedImage[message.id],
                }"
                @click="toggleImage(message.id)"
                alt="Uploaded file"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { getUrlBase } from '../utils';

export default {
  data() {
    return {
      enlargedImage: {},
    };
  },
  computed: {
    messages() {
      return this.$store.getters.getMessagesForActiveChannel;
    },
    activeChannelId() {
      let channel = this.$store.state.activeChannel;
      if (!channel) {
        return null;
      }
      return channel.id;
    }
  },
  watch: {
    messages: {
      handler() {
        this.$nextTick(() => {
          this.scrollToBottom();
        });
      },
      deep: true
    },
    activeChannelId(newChannelId) {
      if (newChannelId) {
        this.fetchMessages(newChannelId);
      }
    }
  },
  methods: {
    fetchMessages(channelId) {
      this.$store.dispatch('fetchMessagesForChannel', channelId);
    },
    getSender(userId) {
      return this.$store.getters.getUserById(userId) || {
        id: userId,
        fullname: `User#${userId}`,
        email: '',
      };
    },
    scrollToBottom() {
      const container = this.$refs.messageContainer;
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    },
    getFileUrl(file) {
      const fileToken = this.$store.state.accessTickets?.fileToken || '';
      return `${getUrlBase()}${file}?token=${fileToken}`;
    },
    toggleImage(messageId) {
      this.enlargedImage[messageId] = !this.enlargedImage[messageId];
      this.enlargedImage = { ...this.enlargedImage };
    },
    getMessageContent(message) {
      // TODO: handle case where user is not logged in
      if (!this.$store.state.user) {
        return '';
      }
      if (message.senderId === this.$store.state.user.id) {
        return message.content;
      } else {
        return message.modifiedContent && message.modifiedContent.trim() !== ''
          ? message.modifiedContent
          : message.content;
      }
    }
  },
  mounted() {
    if (this.activeChannelId) {
      this.fetchMessages(this.activeChannelId);
    }
    this.scrollToBottom();
  },
  updated() {
    this.scrollToBottom();
  }
};
</script>
