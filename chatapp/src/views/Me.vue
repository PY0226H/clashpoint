<template>
  <div class="flex h-screen">
    <Sidebar />
    <div class="flex-1 overflow-y-auto bg-gray-50">
      <div class="max-w-4xl mx-auto p-6 space-y-4">
        <div class="flex items-start justify-between gap-3">
          <div>
            <h1 class="text-2xl font-bold text-gray-900">个人资料</h1>
            <p class="text-sm text-gray-600 mt-1">查看账号信息、通知入口与充值入口。</p>
          </div>
          <button
            @click="refreshMe"
            :disabled="loading"
            class="px-4 py-2 rounded bg-blue-600 text-white text-sm disabled:opacity-50"
          >
            {{ loading ? '刷新中...' : '刷新' }}
          </button>
        </div>

        <div v-if="errorText" class="bg-red-50 text-red-700 border border-red-200 rounded p-3 text-sm">
          {{ errorText }}
        </div>

        <div class="bg-white border rounded-lg p-4 grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
          <div>
            <div class="text-xs uppercase text-gray-500">userId</div>
            <div class="text-gray-900 font-semibold mt-1">{{ user?.id || '-' }}</div>
          </div>
          <div>
            <div class="text-xs uppercase text-gray-500">email</div>
            <div class="text-gray-900 font-semibold mt-1">{{ user?.email || '-' }}</div>
          </div>
          <div>
            <div class="text-xs uppercase text-gray-500">wallet balance</div>
            <div class="text-gray-900 font-semibold mt-1">{{ walletBalance }}</div>
          </div>
        </div>

        <div class="bg-white border rounded-lg p-4">
          <div class="text-sm font-semibold text-gray-900 mb-3">账号密码</div>
          <form class="space-y-3" @submit.prevent="submitSetPassword">
            <div class="text-xs text-gray-600">
              已绑定手机号：{{ boundPhone || '未绑定' }}
            </div>
            <label class="block text-sm text-gray-700">
              新密码
              <input
                v-model="newPassword"
                type="password"
                minlength="6"
                required
                class="mt-1 block w-full px-3 py-2 border rounded-md"
                placeholder="至少 6 位"
              />
            </label>
            <label class="block text-sm text-gray-700">
              确认新密码
              <input
                v-model="confirmPassword"
                type="password"
                minlength="6"
                required
                class="mt-1 block w-full px-3 py-2 border rounded-md"
              />
            </label>
            <label class="block text-sm text-gray-700">
              短信验证码
              <div class="mt-1 flex items-center gap-2">
                <input
                  v-model="smsCode"
                  type="text"
                  class="flex-1 px-3 py-2 border rounded-md"
                  placeholder="6位验证码"
                />
                <button
                  type="button"
                  @click="sendSetPasswordSmsCode"
                  :disabled="smsSending || !hasBoundPhone"
                  class="px-3 py-2 rounded bg-blue-600 text-white text-xs disabled:opacity-50"
                >
                  {{ smsSending ? '发送中...' : '发送验证码' }}
                </button>
              </div>
            </label>
            <p v-if="passwordSmsTips" class="text-xs text-gray-600">{{ passwordSmsTips }}</p>
            <div class="flex items-center gap-3">
              <button
                type="submit"
                :disabled="passwordSaving || !hasBoundPhone"
                class="px-3 py-2 rounded bg-emerald-600 text-white text-sm disabled:opacity-50"
              >
                {{ passwordSaving ? '保存中...' : '设置密码' }}
              </button>
              <span v-if="passwordSuccessText" class="text-sm text-emerald-700">{{ passwordSuccessText }}</span>
            </div>
          </form>
        </div>

        <div class="bg-white border rounded-lg p-4">
          <div class="text-sm font-semibold text-gray-900 mb-3">快捷入口</div>
          <div class="flex flex-wrap gap-2">
            <button
              @click="goTo('/notifications')"
              class="px-3 py-2 rounded border bg-white hover:bg-gray-100 text-sm"
            >
              通知中心
            </button>
            <button
              @click="goTo('/wallet')"
              class="px-3 py-2 rounded bg-blue-600 text-white text-sm"
            >
              前往充值
            </button>
            <button
              @click="goTo('/chat')"
              class="px-3 py-2 rounded border bg-white hover:bg-gray-100 text-sm"
            >
              返回会话
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Sidebar from '../components/Sidebar.vue';
import { validateSetPasswordInput } from '../auth-password-utils.js';

export default {
  components: {
    Sidebar,
  },
  data() {
    return {
      loading: false,
      errorText: '',
      walletBalance: 0,
      newPassword: '',
      confirmPassword: '',
      smsCode: '',
      smsSending: false,
      passwordSmsTips: '',
      passwordSaving: false,
      passwordSuccessText: '',
    };
  },
  computed: {
    user() {
      return this.$store.getters.getUser || null;
    },
    boundPhone() {
      return String(this.user?.phoneE164 || '').trim();
    },
    hasBoundPhone() {
      return !!this.boundPhone;
    },
  },
  methods: {
    async refreshMe() {
      this.loading = true;
      this.errorText = '';
      try {
        const wallet = await this.$store.dispatch('fetchWalletBalance');
        this.walletBalance = Number(wallet?.balance || 0);
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '刷新失败';
      } finally {
        this.loading = false;
      }
    },
    resolvePasswordErrorText(code) {
      if (code === 'required') {
        return '请先输入新密码';
      }
      if (code === 'too_short') {
        return '密码至少需要 6 位';
      }
      if (code === 'mismatch') {
        return '两次输入的密码不一致';
      }
      if (code === 'sms_required') {
        return '请先输入短信验证码';
      }
      return '设置密码失败';
    },
    resolveSetPasswordApiError(error) {
      const code = error?.response?.data?.error || '';
      if (code === 'auth_sms_code_invalid') {
        return '验证码错误，请重试';
      }
      if (code === 'auth_sms_code_expired') {
        return '验证码已过期，请重新发送';
      }
      if (code === 'auth_phone_bind_required') {
        return '当前账号未绑定手机号，请先完成绑定';
      }
      return code || error?.message || '设置密码失败';
    },
    async sendSetPasswordSmsCode() {
      this.errorText = '';
      this.passwordSmsTips = '';
      if (!this.hasBoundPhone) {
        this.errorText = '当前账号未绑定手机号，请先完成绑定';
        return;
      }
      this.smsSending = true;
      try {
        const ret = await this.$store.dispatch('sendSmsCodeV2', {
          phone: this.boundPhone,
          scene: 'bind_phone',
        });
        if (ret?.debugCode) {
          this.passwordSmsTips = `开发环境验证码：${ret.debugCode}`;
        } else {
          this.passwordSmsTips = '验证码已发送，请查收短信。';
        }
      } catch (error) {
        this.errorText = error?.response?.data?.error || error?.message || '发送验证码失败';
      } finally {
        this.smsSending = false;
      }
    },
    async submitSetPassword() {
      this.errorText = '';
      this.passwordSuccessText = '';
      if (!this.hasBoundPhone) {
        this.errorText = '当前账号未绑定手机号，请先完成绑定';
        return;
      }
      const result = validateSetPasswordInput(this.newPassword, this.confirmPassword, this.smsCode);
      if (!result.valid) {
        this.errorText = this.resolvePasswordErrorText(result.code);
        return;
      }
      this.passwordSaving = true;
      try {
        await this.$store.dispatch('setPasswordV2', {
          password: this.newPassword,
          smsCode: this.smsCode,
        });
        this.newPassword = '';
        this.confirmPassword = '';
        this.smsCode = '';
        this.passwordSuccessText = '密码已更新';
      } catch (error) {
        this.errorText = this.resolveSetPasswordApiError(error);
      } finally {
        this.passwordSaving = false;
      }
    },
    async goTo(path) {
      if (this.$route.path === path) {
        return;
      }
      await this.$router.push(path);
    },
  },
  async mounted() {
    await this.refreshMe();
  },
};
</script>
