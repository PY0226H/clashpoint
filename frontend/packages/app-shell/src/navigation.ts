import { isPhoneBindRequired, type useAuthStore } from "@echoisle/auth-sdk";

type AuthSnapshot = Pick<ReturnType<typeof useAuthStore.getState>, "token" | "user">;

export function resolveLandingPath({ token, user }: AuthSnapshot): string {
  if (!token) {
    return "/login";
  }
  if (isPhoneBindRequired(user)) {
    return "/bind-phone";
  }
  return "/home";
}
