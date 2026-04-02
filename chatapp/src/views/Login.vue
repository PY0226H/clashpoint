<template>
  <div class="min-h-screen flex items-center justify-center p-4 sm:p-8">
    <div class="w-full max-w-5xl grid grid-cols-1 lg:grid-cols-2 overflow-hidden rounded-3xl border border-slate-200/80 bg-white/85 backdrop-blur-md shadow-[0_28px_80px_rgba(15,23,42,0.12)]">
      <div class="hidden lg:flex flex-col justify-between p-10 bg-slate-950 text-slate-100">
        <div>
          <div class="text-[11px] uppercase tracking-[0.28em] text-slate-400">EchoIsle</div>
          <h1 class="text-4xl font-semibold mt-3 leading-tight">在线辩论 AI 裁判平台</h1>
          <p class="mt-4 text-sm text-slate-300 leading-relaxed">
            mac 端优先工作台，聚焦赛后判决、平局治理与实时辩论流程。
          </p>
        </div>
        <div class="space-y-3">
          <div class="text-xs text-slate-400">支持登录方式</div>
          <div class="grid grid-cols-3 gap-2 text-xs">
            <div class="rounded-xl border border-slate-700 px-3 py-2 text-center">邮箱</div>
            <div class="rounded-xl border border-slate-700 px-3 py-2 text-center">手机密码</div>
            <div class="rounded-xl border border-slate-700 px-3 py-2 text-center">短信验证码</div>
          </div>
        </div>
      </div>

      <div class="p-6 sm:p-10 space-y-6">
        <div>
          <h2 class="text-3xl font-semibold text-slate-900">登录</h2>
          <p class="text-sm text-slate-600 mt-2">支持邮箱/手机号/验证码登录</p>
        </div>

        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="item in modes"
            :key="item.value"
            type="button"
            @click="mode = item.value"
            class="px-2 py-2 text-xs rounded-xl border transition"
            :class="mode === item.value ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-700 border-slate-300 hover:border-slate-400'"
          >
            {{ item.label }}
          </button>
        </div>

        <form @submit.prevent="login" class="space-y-4">
          <template v-if="mode === 'email_password'">
            <div>
              <label class="block text-sm font-medium text-slate-700">邮箱</label>
              <input v-model="email" type="email" required class="echo-field mt-1" />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700">密码</label>
              <input v-model="password" type="password" required class="echo-field mt-1" />
            </div>
          </template>

          <template v-else-if="mode === 'phone_password'">
            <div>
              <label class="block text-sm font-medium text-slate-700">手机号(+86)</label>
              <input v-model="phone" type="text" required class="echo-field mt-1" />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700">密码</label>
              <input v-model="password" type="password" required class="echo-field mt-1" />
            </div>
          </template>

          <template v-else>
            <div>
              <label class="block text-sm font-medium text-slate-700">手机号(+86)</label>
              <input v-model="phone" type="text" required class="echo-field mt-1" />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-700">验证码</label>
              <div class="mt-1 flex gap-2">
                <input v-model="smsCode" type="text" required class="echo-field flex-1" />
                <button type="button" @click="sendOtpCode" class="echo-btn-secondary text-xs px-3 py-2 whitespace-nowrap">
                  发码
                </button>
              </div>
            </div>
          </template>

          <p v-if="tips" class="text-xs text-slate-600">{{ tips }}</p>
          <p v-if="errorText" class="text-sm text-red-600">{{ errorText }}</p>

          <button type="submit" class="w-full echo-btn-primary py-2.5">
            登录
          </button>
        </form>

        <div class="pt-4 border-t border-slate-200">
          <button
            type="button"
            @click="startWechatLogin"
            class="w-full py-2.5 px-4 text-sm text-white bg-emerald-600 rounded-xl hover:bg-emerald-700 transition"
          >
            微信登录（占位）
          </button>
          <div v-if="wechatState" class="mt-3 space-y-2">
            <p class="text-xs text-slate-500">当前仓库未接入 iOS 微信 SDK，可用 mock code 调试（示例：`mock_user01:union01:昵称`）。</p>
            <input v-model="wechatCode" type="text" placeholder="输入微信授权 code" class="echo-field text-sm" />
            <button type="button" @click="submitWechatSignin" class="w-full py-2 px-4 text-sm text-white bg-emerald-600 rounded-xl hover:bg-emerald-700 transition">
              提交微信授权结果
            </button>
          </div>
        </div>

        <p class="text-center text-sm text-slate-600">
          没有账号？
          <router-link to="/register" class="font-medium text-blue-600 hover:text-blue-500">
            去注册
          </router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
export default {
  data() {
    return {
      mode: 'email_password',
      email: '',
      phone: '',
      password: '',
      smsCode: '',
      tips: '',
      errorText: '',
      wechatState: '',
      wechatCode: '',
      modes: [
        { value: 'email_password', label: '邮箱+密码' },
        { value: 'phone_password', label: '手机+密码' },
        { value: 'phone_otp', label: '手机+验证码' },
      ],
    };
  },
  methods: {
    async sendOtpCode() {
      this.errorText = '';
      this.tips = '';
      try {
        const ret = await this.$store.dispatch('sendSmsCodeV2', {
          phone: this.phone,
          scene: 'signin_phone_otp',
        });
        if (ret?.debugCode) {
          this.tips = `开发环境验证码：${ret.debugCode}`;
        } else {
          this.tips = '验证码已发送，请查收短信。';
        }
      } catch (error) {
        this.errorText = error?.response?.data?.error || '发送验证码失败';
      }
    },
    async login() {
      this.errorText = '';
      this.tips = '';
      try {
        let user = null;
        let accountType = 'unknown';
        let accountIdentifier = '';
        if (this.mode === 'email_password') {
          user = await this.$store.dispatch('signinPasswordV2', {
            account: this.email,
            accountType: 'email',
            password: this.password,
          });
          accountType = 'email';
          accountIdentifier = this.email;
        } else if (this.mode === 'phone_password') {
          user = await this.$store.dispatch('signinPasswordV2', {
            account: this.phone,
            accountType: 'phone',
            password: this.password,
          });
          accountType = 'phone';
          accountIdentifier = this.phone;
        } else {
          user = await this.$store.dispatch('signinOtpV2', {
            phone: this.phone,
            smsCode: this.smsCode,
          });
          accountType = 'phone';
          accountIdentifier = this.phone;
        }
        await this.$store.dispatch('userLogin', {
          accountType,
          accountIdentifier,
          userId: user?.id,
        });
        if (user?.phoneBindRequired) {
          this.$router.push('/bind-phone');
          return;
        }
        this.$router.push('/home');
      } catch (error) {
        this.errorText = error?.response?.data?.error || '登录失败';
      }
    },
    async startWechatLogin() {
      this.errorText = '';
      this.tips = '';
      try {
        const challenge = await this.$store.dispatch('wechatChallengeV2');
        this.wechatState = challenge?.state || '';
        this.tips = '微信授权 challenge 已创建。';
      } catch (error) {
        this.errorText = error?.response?.data?.error || '创建微信授权 challenge 失败';
      }
    },
    async submitWechatSignin() {
      this.errorText = '';
      this.tips = '';
      try {
        const ret = await this.$store.dispatch('wechatSigninV2', {
          state: this.wechatState,
          code: this.wechatCode,
        });
        if (ret?.bindRequired) {
          this.$router.push({
            name: 'Register',
            query: { wechatTicket: ret.wechatTicket || '' },
          });
          return;
        }
        await this.$store.dispatch('userLogin', {
          accountType: 'wechat',
          accountIdentifier: ret?.user?.id ? String(ret.user.id) : '',
          userId: ret?.user?.id,
        });
        if (ret?.user?.phoneBindRequired) {
          this.$router.push('/bind-phone');
          return;
        }
        this.$router.push('/home');
      } catch (error) {
        this.errorText = error?.response?.data?.error || '微信登录失败';
      }
    },
  },
};
</script>
