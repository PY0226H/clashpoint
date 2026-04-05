import { FormEvent, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@echoisle/auth-sdk";
import { Button, InlineHint, SectionTitle, TextField } from "@echoisle/ui";

export function PhoneBindPage() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const loading = useAuthStore((state) => state.loading);
  const error = useAuthStore((state) => state.error);
  const clearError = useAuthStore((state) => state.clearError);
  const sendBindSmsCode = useAuthStore((state) => state.sendBindSmsCode);
  const bindPhone = useAuthStore((state) => state.bindPhone);
  const logout = useAuthStore((state) => state.logout);
  const [phone, setPhone] = useState(user?.phoneE164 || "+8613900000000");
  const [smsCode, setSmsCode] = useState("");
  const [cooldownLeft, setCooldownLeft] = useState(0);
  const [debugCode, setDebugCode] = useState<string | null>(null);
  const [sentHint, setSentHint] = useState<string | null>(null);

  const canSendCode = useMemo(() => cooldownLeft <= 0 && !!phone.trim(), [cooldownLeft, phone]);
  const canSubmit = useMemo(
    () => !loading && !!phone.trim() && !!smsCode.trim(),
    [loading, phone, smsCode]
  );

  useEffect(() => {
    if (cooldownLeft <= 0) {
      return;
    }
    const timer = window.setTimeout(() => {
      setCooldownLeft((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearTimeout(timer);
  }, [cooldownLeft]);

  async function onSendCode() {
    clearError();
    setSentHint(null);
    try {
      const result = await sendBindSmsCode(phone.trim());
      setCooldownLeft(result.cooldownSecs || 60);
      setDebugCode(result.debugCode || null);
      setSentHint("Verification code sent. Please complete phone binding.");
    } catch {
      // Error state is maintained in auth store.
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    clearError();
    try {
      await bindPhone({
        phone: phone.trim(),
        smsCode: smsCode.trim()
      });
      navigate("/home", { replace: true });
    } catch {
      // Error state is maintained in auth store.
    }
  }

  return (
    <section className="echo-bind-page">
      <SectionTitle>Phone Binding Required</SectionTitle>
      <p>
        Your account is signed in. Complete phone binding to unlock Lobby, Room, Wallet, and Ops paths.
      </p>
      <form className="echo-bind-form" onSubmit={onSubmit}>
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
          <TextField
            onChange={(event) => setSmsCode(event.target.value)}
            placeholder="Enter 6-digit code"
            value={smsCode}
          />
        </label>
        <div className="echo-bind-actions">
          <Button disabled={!canSendCode} onClick={onSendCode} type="button">
            {cooldownLeft > 0 ? `Resend in ${cooldownLeft}s` : "Send Code"}
          </Button>
          <Button disabled={!canSubmit} type="submit">
            {loading ? "Binding..." : "Bind Phone"}
          </Button>
          <Button onClick={() => navigate("/login", { replace: true })} type="button">
            Back to Login
          </Button>
          <Button
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
            type="button"
          >
            Sign Out
          </Button>
        </div>
        {sentHint ? <InlineHint>{sentHint}</InlineHint> : null}
        {debugCode ? <InlineHint>Debug code: {debugCode}</InlineHint> : null}
        {error ? <p className="echo-error">{error}</p> : null}
      </form>
      <div className="echo-bind-tips">
        <InlineHint>
          Current account: {user?.email || user?.fullname || "super@none.org"}.
        </InlineHint>
        <InlineHint>
          Binding scene uses backend contract `scene=bind_phone`.
        </InlineHint>
      </div>
    </section>
  );
}
