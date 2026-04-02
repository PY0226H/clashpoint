<template>
  <div class="relative flex flex-col bg-white/80 px-3 py-3">
    <div class="flex items-center mb-2">
      <button
        @click="triggerFileUpload"
        class="mr-2 rounded-lg border border-slate-200 px-2 py-1.5 text-slate-600 hover:border-slate-300 hover:text-blue-600 transition"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </button>
      <input
        type="file"
        ref="fileInput"
        @change="handleFileUpload"
        multiple
        accept="image/*"
        class="hidden"
      />
      <div class="text-xs text-slate-500">支持上传图片后随消息发送</div>
    </div>

    <div>
      <textarea
        v-model="message"
        @keydown.enter.exact.prevent="sendMessage"
        placeholder="输入消息并按 Enter 发送（Shift+Enter 可换行）"
        class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 resize-none pr-14"
        rows="3"
      ></textarea>
    </div>

    <div v-if="files.length > 0" class="flex flex-wrap gap-2 pt-2">
      <img
        v-for="file in files"
        :key="file.path"
        :src="file.fullUrl"
        class="h-24 w-24 object-cover rounded-lg border border-slate-200"
        alt="Uploaded image"
      />
    </div>

    <button
      @click="sendMessage"
      class="absolute bottom-5 right-5 p-2 text-white bg-blue-600 rounded-full hover:bg-blue-700 focus:outline-none shadow-sm"
      aria-label="发送消息"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        class="w-5 h-5"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M5 12h14M12 5l7 7-7 7"
        />
      </svg>
    </button>
  </div>
</template>

<script lang="ts">
export default {
  data() {
    return {
      message: '',
      files: [],
    };
  },
  computed: {
    userId() {
      return this.$store.state.user.id;
    },
    activeChannelId() {
      const channel = this.$store.state.activeChannel;
      if (!channel) {
        return null;
      }
      return channel.id;
    },
  },
  methods: {
    async sendMessage() {
      if (this.message.trim() === '') return;
      if (!this.activeChannelId) {
        console.warn('No active channel selected, skip send');
        return;
      }

      const payload = {
        chatId: this.activeChannelId,
        content: this.message,
        files: this.files.map(file => file.path),
      };

      console.log('Sending message:', payload);

      try {
        await this.$store.dispatch('sendMessage', payload);
        this.$store.dispatch('messageSent', { chatId: payload.chatId, type: "text", size: payload.content.length, totalFiles: payload.files.length });
        this.message = ''; // Clear the input after sending
        this.files = []; // Clear the files after sending
      } catch (error) {
        console.error('Failed to send message:', error);
      }
    },
    triggerFileUpload() {
      this.$refs.fileInput.click();
    },
    async handleFileUpload(event) {
      const files = Array.from(event.target.files);
      if (files.length === 0) return;

      try {
        const uploadedFiles = await this.$store.dispatch('uploadFiles', files);
        this.files = [...this.files, ...uploadedFiles];
      } catch (error) {
        console.error('Failed to upload files:', error);
      }
    },
  },
};
</script>
