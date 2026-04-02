<template>
  <div class="echo-auth-shell">
    <div class="echo-auth-card space-y-6 echo-fade-in">
      <h1 class="text-2xl font-semibold text-slate-900 text-center">绑定手机号</h1>
      <p class="text-sm text-slate-600 text-center">
        为了继续使用功能，请先完成手机号验证码绑定（仅支持中国大陆 +86）。
      </p>

      <form @submit.prevent="bindPhone" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700">手机号</label>
          <input
            v-model="phone"
            type="text"
            placeholder="13800138000"
            required
            class="mt-1 echo-field"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-700">验证码</label>
          <div class="mt-1 flex gap-2">
            <input
              v-model="smsCode"
              type="text"
              placeholder="6位验证码"
              required
              class="echo-field flex-1"
            />
            <button
              type="button"
              @click="sendCode"
              :disabled="sendingCode || submitting"
              class="echo-btn-secondary px-3 py-2 text-sm whitespace-nowrap"
            >
              {{ sendingCode ? '发送中...' : '发送验证码' }}
            </button>
          </div>
        </div>

        <p v-if="tips" class="echo-feedback echo-feedback-info text-xs">{{ tips }}</p>
        <p v-if="errorText" class="echo-feedback echo-feedback-error">{{ errorText }}</p>

        <button
          type="submit"
          :disabled="submitting || sendingCode"
          class="echo-btn-primary w-full py-2 px-4"
        >
          {{ submitting ? '绑定中...' : '绑定并继续' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script lang="ts">
export default {
  data() {
    return {
      phone: '',
      smsCode: '',
      tips: '',
      errorText: '',
      sendingCode: false,
      submitting: false,
    };
  },
  methods: {
    async sendCode() {
      this.errorText = '';
      this.tips = '';
      this.sendingCode = true;
      try {
        const ret = await this.$store.dispatch('sendSmsCodeV2', {
          phone: this.phone,
          scene: 'bind_phone',
        });
        if (ret?.debugCode) {
          this.tips = `开发环境验证码：${ret.debugCode}`;
        } else {
          this.tips = '验证码已发送，请查收短信。';
        }
      } catch (error) {
        this.errorText = error?.response?.data?.error || '发送验证码失败';
      } finally {
        this.sendingCode = false;
      }
    },
    async bindPhone() {
      this.errorText = '';
      this.submitting = true;
      try {
        await this.$store.dispatch('bindPhoneV2', {
          phone: this.phone,
          smsCode: this.smsCode,
        });
        this.$router.push('/home');
      } catch (error) {
        this.errorText = error?.response?.data?.error || '绑定失败';
      } finally {
        this.submitting = false;
      }
    },
  },
};
</script>
