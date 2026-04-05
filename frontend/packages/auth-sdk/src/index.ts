import {
  bindWechatPhone as bindWechatPhoneApi,
  bindPhone as bindPhoneApi,
  createAccessTickets,
  requestWechatChallenge as requestWechatChallengeApi,
  refreshSession as refreshSessionApi,
  sendSmsCode,
  signinOtp,
  signinPassword,
  signinWechat as signinWechatApi,
  type AccessTicketsResponse,
  type AccountType,
  type AuthUser,
  type AuthResponse,
  type SendSmsCodeResponse,
  type WechatChallengeResponse,
  type WechatSigninResponse,
  setAccessToken,
  toApiError
} from "@echoisle/api-client";
import { create } from "zustand";
import { persist } from "zustand/middleware";

let lastBootstrapToken: string | null = null;

export type AccessTickets = AccessTicketsResponse & {
  expireAt: number;
};

type AuthState = {
  token: string | null;
  user: AuthUser | null;
  accessTickets: AccessTickets | null;
  wechatChallenge: WechatChallengeResponse | null;
  wechatBindTicket: string | null;
  loading: boolean;
  error: string | null;
  clearError: () => void;
  signInPassword: (payload: { account: string; accountType: AccountType; password: string }) => Promise<void>;
  signInOtp: (payload: { phone: string; smsCode: string }) => Promise<void>;
  requestWechatChallenge: () => Promise<WechatChallengeResponse>;
  signInWechat: (payload: { code: string; state?: string }) => Promise<{ bindRequired: boolean; wechatTicket?: string }>;
  bindPhoneWithWechatTicket: (payload: { phone: string; smsCode: string; password?: string; fullname?: string }) => Promise<void>;
  sendSigninOtpCode: (phone: string) => Promise<SendSmsCodeResponse>;
  sendBindSmsCode: (phone: string) => Promise<SendSmsCodeResponse>;
  bindPhone: (payload: { phone: string; smsCode: string }) => Promise<void>;
  refreshSession: () => Promise<string>;
  refreshAccessTickets: (force?: boolean) => Promise<AccessTickets | null>;
  bootstrapSession: () => Promise<void>;
  logout: () => void;
};

function resolvePhoneBindRequired(user: AuthUser | null): boolean {
  if (!user) {
    return false;
  }
  if (Object.prototype.hasOwnProperty.call(user, "phoneBindRequired")) {
    return Boolean(user.phoneBindRequired);
  }
  return !String(user.phoneE164 || "").trim();
}

export function normalizeAuthUserForPhoneGate(user: AuthUser): AuthUser {
  return {
    ...user,
    phoneBindRequired: resolvePhoneBindRequired(user)
  };
}

export function isPhoneBindRequired(user: AuthUser | null): boolean {
  return resolvePhoneBindRequired(user);
}

function toAccessTicketsState(data: AccessTicketsResponse): AccessTickets {
  return {
    ...data,
    expireAt: Date.now() + data.expiresInSecs * 1000
  };
}

async function toSignedInState(data: AuthResponse): Promise<{ token: string; user: AuthUser; accessTickets: AccessTickets | null }> {
  setAccessToken(data.accessToken);
  let accessTickets: AccessTickets | null = null;
  try {
    accessTickets = toAccessTicketsState(await createAccessTickets());
  } catch {
    // Login succeeds even if ticket refresh is temporarily unavailable.
  }
  return {
    token: data.accessToken,
    user: normalizeAuthUserForPhoneGate(data.user),
    accessTickets
  };
}

export type WechatSigninOutcome =
  | {
      bindRequired: true;
      wechatTicket: string | null;
    }
  | {
      bindRequired: false;
      auth: AuthResponse;
    };

export function resolveWechatSigninOutcome(data: WechatSigninResponse): WechatSigninOutcome {
  if (data.bindRequired) {
    return {
      bindRequired: true,
      wechatTicket: data.wechatTicket || null
    };
  }
  if (!data.accessToken || !data.user) {
    throw new Error("auth_wechat_response_invalid");
  }
  return {
    bindRequired: false,
    auth: {
      accessToken: data.accessToken,
      tokenType: data.tokenType,
      expiresInSecs: data.expiresInSecs,
      user: data.user
    }
  };
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      accessTickets: null,
      wechatChallenge: null,
      wechatBindTicket: null,
      loading: false,
      error: null,
      clearError: () => set({ error: null }),
      signInPassword: async ({ account, accountType, password }) => {
        set({ loading: true, error: null });
        try {
          const data = await signinPassword({ account, accountType, password });
          const session = await toSignedInState(data);
          set({
            token: session.token,
            user: session.user,
            accessTickets: session.accessTickets,
            loading: false,
            error: null
          });
        } catch (error) {
          set({ loading: false, error: toApiError(error) });
          throw error;
        }
      },
      signInOtp: async ({ phone, smsCode }) => {
        set({ loading: true, error: null });
        try {
          const data = await signinOtp({ phone, smsCode });
          const session = await toSignedInState(data);
          set({
            token: session.token,
            user: session.user,
            accessTickets: session.accessTickets,
            loading: false,
            error: null
          });
        } catch (error) {
          set({ loading: false, error: toApiError(error) });
          throw error;
        }
      },
      requestWechatChallenge: async () => {
        set({ loading: true, error: null });
        try {
          const challenge = await requestWechatChallengeApi();
          set({ wechatChallenge: challenge, loading: false, error: null });
          return challenge;
        } catch (error) {
          set({ loading: false, error: toApiError(error) });
          throw error;
        }
      },
      signInWechat: async ({ code, state }) => {
        set({ loading: true, error: null });
        try {
          const challengeState = state?.trim() || get().wechatChallenge?.state;
          if (!challengeState) {
            throw new Error("auth_wechat_challenge_missing");
          }
          const response = await signinWechatApi({
            state: challengeState,
            code: code.trim()
          });
          const outcome = resolveWechatSigninOutcome(response);
          if (outcome.bindRequired) {
            set({
              loading: false,
              error: null,
              wechatBindTicket: outcome.wechatTicket
            });
            return {
              bindRequired: true,
              wechatTicket: outcome.wechatTicket || undefined
            };
          }
          const session = await toSignedInState(outcome.auth);
          set({
            token: session.token,
            user: session.user,
            accessTickets: session.accessTickets,
            loading: false,
            error: null,
            wechatBindTicket: null
          });
          return { bindRequired: false };
        } catch (error) {
          set({ loading: false, error: toApiError(error) });
          throw error;
        }
      },
      bindPhoneWithWechatTicket: async ({ phone, smsCode, password, fullname }) => {
        set({ loading: true, error: null });
        try {
          const ticket = get().wechatBindTicket;
          if (!ticket) {
            throw new Error("auth_wechat_bind_required");
          }
          const response = await bindWechatPhoneApi({
            wechatTicket: ticket,
            phone: phone.trim(),
            smsCode: smsCode.trim(),
            password: password?.trim() || undefined,
            fullname: fullname?.trim() || undefined
          });
          const outcome = resolveWechatSigninOutcome(response);
          if (outcome.bindRequired) {
            set({
              loading: false,
              error: null,
              wechatBindTicket: outcome.wechatTicket
            });
            throw new Error("auth_wechat_bind_required");
          }
          const session = await toSignedInState(outcome.auth);
          set({
            token: session.token,
            user: session.user,
            accessTickets: session.accessTickets,
            wechatBindTicket: null,
            wechatChallenge: null,
            loading: false,
            error: null
          });
        } catch (error) {
          set({ loading: false, error: toApiError(error) });
          throw error;
        }
      },
      sendSigninOtpCode: async (phone) => {
        set({ error: null });
        try {
          return await sendSmsCode({
            phone,
            scene: "signin_phone_otp"
          });
        } catch (error) {
          set({ error: toApiError(error) });
          throw error;
        }
      },
      sendBindSmsCode: async (phone) => {
        set({ error: null });
        try {
          return await sendSmsCode({
            phone,
            scene: "bind_phone"
          });
        } catch (error) {
          set({ error: toApiError(error) });
          throw error;
        }
      },
      bindPhone: async ({ phone, smsCode }) => {
        set({ loading: true, error: null });
        try {
          const result = await bindPhoneApi({ phone, smsCode });
          const normalized = normalizeAuthUserForPhoneGate({
            ...result.user,
            phoneBindRequired: false
          });
          set({ user: normalized, loading: false, error: null });
        } catch (error) {
          set({ loading: false, error: toApiError(error) });
          throw error;
        }
      },
      refreshSession: async () => {
        const token = get().token;
        if (!token) {
          throw new Error("missing access token for refresh");
        }
        try {
          const refreshed = await refreshSessionApi();
          setAccessToken(refreshed.accessToken);
          set({ token: refreshed.accessToken, error: null });
          await get().refreshAccessTickets(true);
          return refreshed.accessToken;
        } catch (error) {
          set({ error: toApiError(error) });
          throw error;
        }
      },
      refreshAccessTickets: async (force = false) => {
        const token = get().token;
        if (!token) {
          set({ accessTickets: null });
          return null;
        }
        const current = get().accessTickets;
        if (!force && current && current.expireAt > Date.now() + 30_000) {
          return current;
        }
        try {
          const next = toAccessTicketsState(await createAccessTickets());
          set({ accessTickets: next, error: null });
          return next;
        } catch (error) {
          set({ error: toApiError(error) });
          throw error;
        }
      },
      bootstrapSession: async () => {
        const token = get().token;
        if (!token || token === lastBootstrapToken) {
          return;
        }
        lastBootstrapToken = token;
        set({ loading: true, error: null });
        try {
          await get().refreshSession();
        } catch {
          get().logout();
        } finally {
          set({ loading: false });
        }
      },
      logout: () => {
        lastBootstrapToken = null;
        setAccessToken(null);
        set({
          token: null,
          user: null,
          accessTickets: null,
          wechatChallenge: null,
          wechatBindTicket: null,
          error: null,
          loading: false
        });
      }
    }),
    {
      name: "echoisle-react-auth",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        accessTickets: state.accessTickets,
        wechatBindTicket: state.wechatBindTicket
      }),
      onRehydrateStorage: () => (state) => {
        if (state?.token) {
          setAccessToken(state.token);
          return;
        }
        setAccessToken(null);
      }
    }
  )
);
