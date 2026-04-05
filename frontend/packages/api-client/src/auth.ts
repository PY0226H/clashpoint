import { http } from "./http";

export type AccountType = "email" | "phone";

export type AuthUser = {
  id: number;
  fullname?: string;
  email?: string;
  phoneE164?: string;
  phoneBindRequired?: boolean;
};

export type SigninPasswordRequest = {
  account: string;
  accountType: AccountType;
  password: string;
};

export type AuthResponse = {
  accessToken: string;
  tokenType?: string;
  expiresInSecs?: number;
  user: AuthUser;
};

export async function signinPassword(payload: SigninPasswordRequest): Promise<AuthResponse> {
  const response = await http.post<AuthResponse>("/auth/v2/signin/password", payload);
  return response.data;
}

export type SigninOtpRequest = {
  phone: string;
  smsCode: string;
};

export async function signinOtp(payload: SigninOtpRequest): Promise<AuthResponse> {
  const response = await http.post<AuthResponse>("/auth/v2/signin/otp", payload);
  return response.data;
}

export type WechatChallengeResponse = {
  state: string;
  expiresInSecs: number;
  appId: string;
};

export type WechatSigninRequest = {
  state: string;
  code: string;
};

export type WechatSigninResponse = {
  bindRequired: boolean;
  wechatTicket?: string;
  accessToken?: string;
  tokenType?: string;
  expiresInSecs?: number;
  user?: AuthUser;
};

export async function requestWechatChallenge(): Promise<WechatChallengeResponse> {
  const response = await http.post<WechatChallengeResponse>("/auth/v2/wechat/challenge");
  return response.data;
}

export async function signinWechat(payload: WechatSigninRequest): Promise<WechatSigninResponse> {
  const response = await http.post<WechatSigninResponse>("/auth/v2/wechat/signin", payload);
  return response.data;
}

export type RefreshResponse = {
  accessToken: string;
  tokenType: string;
  expiresInSecs: number;
};

export type AccessTicketsResponse = {
  fileToken: string;
  notifyToken: string;
  expiresInSecs: number;
};

export type SmsScene = "signup_phone" | "bind_phone" | "signin_phone_otp";

export type SendSmsCodeRequest = {
  phone: string;
  scene: SmsScene;
};

export type SendSmsCodeResponse = {
  sent: boolean;
  ttlSecs: number;
  cooldownSecs: number;
  debugCode?: string;
  providerMessageId?: string;
  providerAcceptedAt?: string;
};

export type BindPhoneRequest = {
  phone: string;
  smsCode: string;
};

export type BindPhoneResponse = {
  bound: boolean;
  user: AuthUser;
};

export async function refreshSession(): Promise<RefreshResponse> {
  const response = await http.post<RefreshResponse>(
    "/auth/refresh",
    null,
    {
      headers: {
        "x-requested-with": "XMLHttpRequest"
      }
    }
  );
  return response.data;
}

export async function createAccessTickets(): Promise<AccessTicketsResponse> {
  const response = await http.post<AccessTicketsResponse>("/tickets");
  return response.data;
}

export async function sendSmsCode(payload: SendSmsCodeRequest): Promise<SendSmsCodeResponse> {
  const response = await http.post<SendSmsCodeResponse>("/auth/v2/sms/send", payload);
  return response.data;
}

export async function bindPhone(payload: BindPhoneRequest): Promise<BindPhoneResponse> {
  const response = await http.post<BindPhoneResponse>("/auth/v2/phone/bind", payload);
  return response.data;
}
