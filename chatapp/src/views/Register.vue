<template>
  <div class="echo-auth-shell">
    <div class="echo-auth-card space-y-6 echo-fade-in">
      <h1 class="text-3xl font-semibold text-center text-slate-900">
        {{ wechatTicket ? '微信绑定手机号' : '注册账号' }}
      </h1>

      <template v-if="!wechatTicket">
        <div class="grid grid-cols-2 gap-2 p-1 rounded-2xl bg-slate-100/70 border border-slate-200/80">
          <button
            type="button"
            @click="mode = 'phone_signup'"
            class="px-2 py-2 text-xs rounded-xl border transition"
            :class="mode === 'phone_signup' ? 'bg-gradient-to-r from-[#0f6adf] to-[#3085f2] text-white border-[#0f6adf]' : 'bg-white/90 text-slate-700 border-slate-300'"
          >
            手机号注册
          </button>
          <button
            type="button"
            @click="mode = 'email_signup'"
            class="px-2 py-2 text-xs rounded-xl border transition"
            :class="mode === 'email_signup' ? 'bg-gradient-to-r from-[#0f6adf] to-[#3085f2] text-white border-[#0f6adf]' : 'bg-white/90 text-slate-700 border-slate-300'"
          >
            邮箱注册(绑手机)
          </button>
        </div>
      </template>

      <form @submit.prevent="register" class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700">昵称</label>
          <input v-model="fullName" type="text" required class="mt-1 echo-field" />
        </div>

        <div v-if="mode === 'email_signup'">
          <label class="block text-sm font-medium text-slate-700">邮箱</label>
          <input v-model="email" type="email" required class="mt-1 echo-field" />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700">手机号(+86)</label>
          <input v-model="phone" type="text" required class="mt-1 echo-field" />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700">
            {{ wechatTicket ? '密码（可选）' : '密码' }}
          </label>
          <input
            v-model="password"
            type="password"
            :required="!wechatTicket"
            class="mt-1 echo-field"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700">验证码</label>
          <div class="mt-1 flex gap-2">
            <input v-model="smsCode" type="text" required class="echo-field flex-1" />
            <button type="button" @click="sendCode" class="echo-btn-secondary px-3 py-2 text-xs whitespace-nowrap">
              发码
            </button>
          </div>
        </div>

        <p v-if="tips" class="text-xs text-slate-600">{{ tips }}</p>
        <p v-if="errorText" class="text-sm text-red-600">{{ errorText }}</p>

        <button type="submit" class="echo-btn-primary w-full py-2 px-4 text-sm">
          {{ wechatTicket ? '绑定并创建账号' : '注册' }}
        </button>
      </form>

      <p v-if="!wechatTicket" class="text-center text-sm text-slate-600">
        已有账号？
        <router-link to="/login" class="font-medium text-[#0f6adf] hover:text-[#0a5ac1]">
          去登录
        </router-link>
      </p>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      mode: 'phone_signup',
      fullName: '',
      email: '',
      phone: '',
      password: '',
      smsCode: '',
      tips: '',
      errorText: '',
      wechatTicket: '',
    };
  },
  mounted() {
    this.wechatTicket = (this.$route?.query?.wechatTicket || '').toString();
    if (this.wechatTicket) {
      this.mode = 'wechat_bind';
    }
  },
  methods: {
    async sendCode() {
      this.errorText = '';
      this.tips = '';
      const scene = this.mode === 'phone_signup' ? 'signup_phone' : 'bind_phone';
      try {
        const ret = await this.$store.dispatch('sendSmsCodeV2', {
          phone: this.phone,
          scene,
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
    async register() {
      this.errorText = '';
      this.tips = '';
      try {
        let user = null;
        let accountType = 'unknown';
        let accountIdentifier = '';
        if (this.wechatTicket) {
          const ret = await this.$store.dispatch('wechatBindPhoneV2', {
            wechatTicket: this.wechatTicket,
            phone: this.phone,
            smsCode: this.smsCode,
            password: this.password,
            fullname: this.fullName,
          });
          user = ret?.user;
          accountType = 'wechat';
          accountIdentifier = this.phone;
        } else if (this.mode === 'phone_signup') {
          user = await this.$store.dispatch('signupPhoneV2', {
            phone: this.phone,
            smsCode: this.smsCode,
            password: this.password,
            fullname: this.fullName,
          });
          accountType = 'phone';
          accountIdentifier = this.phone;
        } else {
          user = await this.$store.dispatch('signupEmailV2', {
            email: this.email,
            phone: this.phone,
            smsCode: this.smsCode,
            password: this.password,
            fullname: this.fullName,
          });
          accountType = 'email';
          accountIdentifier = this.email;
        }
        await this.$store.dispatch('userRegister', {
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
        this.errorText = error?.response?.data?.error || '注册失败';
      }
    },
  },
};
</script>
