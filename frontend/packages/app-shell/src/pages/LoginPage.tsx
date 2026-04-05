import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@echoisle/auth-sdk";
import { Button, InlineHint, TextField } from "@echoisle/ui";
import { resolveLandingPath } from "../navigation";

export function LoginPage() {
  const navigate = useNavigate();
  const loading = useAuthStore((state) => state.loading);
  const error = useAuthStore((state) => state.error);
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const signInPassword = useAuthStore((state) => state.signInPassword);
  const signInOtp = useAuthStore((state) => state.signInOtp);
  const sendSigninOtpCode = useAuthStore((state) => state.sendSigninOtpCode);
  const wechatChallenge = useAuthStore((state) => state.wechatChallenge);
  const wechatBindTicket = useAuthStore((state) => state.wechatBindTicket);
  const requestWechatChallenge = useAuthStore((state) => state.requestWechatChallenge);
  const signInWechat = useAuthStore((state) => state.signInWechat);
  const clearError = useAuthStore((state) => state.clearError);

  const [authMode, setAuthMode] = useState<"password" | "otp" | "wechat">("password");
  const [accountType, setAccountType] = useState<"email" | "phone">("email");
  const [account, setAccount] = useState("super@none.org");
  const [password, setPassword] = useState("EchoSuper@123456");
  const [phone, setPhone] = useState("+86139000000000");
  const [smsCode, setSmsCode] = useState("");
  const [smsCooldown, setSmsCooldown] = useState(0);
  const [wechatCode, setWechatCode] = useState("");
  const [wechatHint, setWechatHint] = useState<string | null>(null);
  const [debugCode, setDebugCode] = useState<string | null>(null);

  const heroHint = useMemo(() => {
    if (authMode === "wechat") {
      return "Use WeChat challenge + code for local placeholder sign-in.";
    }
    if (authMode === "otp") {
      return "Use phone + SMS OTP for local sign-in.";
    }
    return accountType === "email" ? "Use email/password for local sign-in." : "Use phone/password for local sign-in.";
  }, [accountType, authMode]);

  useEffect(() => {
    const target = resolveLandingPath({ token, user, wechatBindTicket });
    if (target !== "/login") {
      navigate(target, { replace: true });
    }
  }, [token, user, wechatBindTicket, navigate]);

  useEffect(() => {
    if (smsCooldown <= 0) {
      return;
    }
    const timer = window.setTimeout(() => {
      setSmsCooldown((prev) => Math.max(0, prev - 1));
    }, 1_000);
    return () => window.clearTimeout(timer);
  }, [smsCooldown]);

  useEffect(() => {
    clearError();
    setDebugCode(null);
    setWechatHint(null);
  }, [authMode, clearError]);

  async function onRequestWechatChallenge() {
    try {
      const challenge = await requestWechatChallenge();
      setWechatHint(`Challenge ready, appId=${challenge.appId}`);
    } catch {
      // error state is handled by auth store.
    }
  }

  async function onSendOtpCode() {
    try {
      const result = await sendSigninOtpCode(phone.trim());
      setSmsCooldown(Math.max(1, result.cooldownSecs || 60));
      setDebugCode(result.debugCode || null);
    } catch {
      // error state is handled by auth store.
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      if (authMode === "otp") {
        await signInOtp({ phone: phone.trim(), smsCode: smsCode.trim() });
      } else if (authMode === "wechat") {
        const outcome = await signInWechat({
          code: wechatCode.trim()
        });
        if (outcome.bindRequired) {
          setWechatHint("WeChat account requires phone bind flow. Ticket is ready for the next bind page integration.");
          return;
        }
      } else {
        await signInPassword({ account, accountType, password });
      }
      const target = resolveLandingPath(useAuthStore.getState());
      navigate(target, { replace: true });
    } catch {
      // error state is handled by auth store.
    }
  }

  const canSubmit =
    authMode === "otp"
      ? !loading && Boolean(phone.trim()) && Boolean(smsCode.trim())
      : authMode === "wechat"
        ? !loading && Boolean(wechatChallenge?.state) && Boolean(wechatCode.trim())
        : !loading && Boolean(account.trim()) && Boolean(password);

  return (
    <div className="echo-login-stage">
      <section className="echo-login-hero">
        <p className="echo-kicker">Mac + Web Refactor Baseline</p>
        <h1>EchoIsle Frontend is now React + TypeScript strict.</h1>
        <p>
          This is the new authentication entrypoint for the three-end migration. Desktop and Web share one route,
          one auth SDK, and one visual system.
        </p>
      </section>

      <form className="echo-login-form" onSubmit={onSubmit}>
        <label>
          Auth Method
          <div className="echo-type-switch" role="group" aria-label="auth method">
            <button
              className={authMode === "password" ? "is-selected" : ""}
              onClick={() => setAuthMode("password")}
              type="button"
            >
              Password
            </button>
            <button className={authMode === "otp" ? "is-selected" : ""} onClick={() => setAuthMode("otp")} type="button">
              SMS OTP
            </button>
            <button
              className={authMode === "wechat" ? "is-selected" : ""}
              onClick={() => setAuthMode("wechat")}
              type="button"
            >
              WeChat
            </button>
          </div>
        </label>

        {authMode === "password" ? (
          <>
            <label>
              Account Type
              <div className="echo-type-switch" role="group" aria-label="account type">
                <button
                  className={accountType === "email" ? "is-selected" : ""}
                  onClick={() => setAccountType("email")}
                  type="button"
                >
                  Email
                </button>
                <button
                  className={accountType === "phone" ? "is-selected" : ""}
                  onClick={() => setAccountType("phone")}
                  type="button"
                >
                  Phone
                </button>
              </div>
            </label>
            <label>
              Account
              <TextField
                autoComplete="username"
                onChange={(event) => setAccount(event.target.value)}
                placeholder={accountType === "email" ? "super@none.org" : "+8613900000000"}
                value={account}
              />
            </label>
            <label>
              Password
              <TextField
                autoComplete="current-password"
                onChange={(event) => setPassword(event.target.value)}
                placeholder="********"
                type="password"
                value={password}
              />
            </label>
          </>
        ) : authMode === "otp" ? (
          <>
            <label>
              Phone
              <TextField
                autoComplete="tel"
                onChange={(event) => setPhone(event.target.value)}
                placeholder="+8613900000000"
                value={phone}
              />
            </label>
            <label>
              SMS Code
              <div className="echo-inline-row">
                <TextField
                  autoComplete="one-time-code"
                  onChange={(event) => setSmsCode(event.target.value)}
                  placeholder="123456"
                  value={smsCode}
                />
                <Button
                  className="echo-inline-btn"
                  disabled={loading || smsCooldown > 0 || !phone.trim()}
                  onClick={onSendOtpCode}
                  type="button"
                >
                  {smsCooldown > 0 ? `${smsCooldown}s` : "Send Code"}
                </Button>
              </div>
            </label>
            {debugCode ? <InlineHint>Debug OTP: {debugCode}</InlineHint> : null}
          </>
        ) : (
          <>
            <label>
              WeChat Challenge
              <div className="echo-inline-row">
                <TextField
                  readOnly
                  value={wechatChallenge?.state || "No challenge yet"}
                />
                <Button className="echo-inline-btn" disabled={loading} onClick={onRequestWechatChallenge} type="button">
                  {wechatChallenge ? "Refresh" : "Get Challenge"}
                </Button>
              </div>
            </label>
            <label>
              WeChat Auth Code
              <TextField
                onChange={(event) => setWechatCode(event.target.value)}
                placeholder="Paste WeChat code"
                value={wechatCode}
              />
            </label>
            {wechatHint ? <InlineHint>{wechatHint}</InlineHint> : null}
            {wechatBindTicket ? <InlineHint>Bind Ticket: {wechatBindTicket}</InlineHint> : null}
          </>
        )}

        <InlineHint>{heroHint}</InlineHint>
        {error ? <p className="echo-error">{error}</p> : null}
        <Button disabled={!canSubmit} type="submit">
          {loading ? "Signing in..." : authMode === "otp" ? "Sign In with OTP" : authMode === "wechat" ? "Sign In with WeChat" : "Sign In"}
        </Button>
      </form>
    </div>
  );
}
