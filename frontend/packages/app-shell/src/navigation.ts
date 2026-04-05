import { isPhoneBindRequired, type useAuthStore } from "@echoisle/auth-sdk";

type AuthSnapshot = Pick<ReturnType<typeof useAuthStore.getState>, "token" | "user" | "wechatBindTicket">;

export function resolveLandingPath({ token, user, wechatBindTicket }: AuthSnapshot): string {
  if (!token && wechatBindTicket) {
    return "/bind-phone";
  }
  if (!token) {
    return "/login";
  }
  if (isPhoneBindRequired(user)) {
    return "/bind-phone";
  }
  return "/home";
}
