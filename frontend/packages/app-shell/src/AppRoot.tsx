import { useEffect } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { isPhoneBindRequired, useAuthStore } from "@echoisle/auth-sdk";
import "@echoisle/tokens/tokens.css";
import "@echoisle/ui/styles.css";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/AppLayout";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PhoneBindPage } from "./pages/PhoneBindPage";
import { DebateLobbyPage } from "./pages/DebateLobbyPage";
import { DebateRoomPage } from "./pages/DebateRoomPage";
import { WalletPage } from "./pages/WalletPage";
import { OpsConsolePage } from "./pages/OpsConsolePage";
import { resolveLandingPath } from "./navigation";
import "./styles.css";

const queryClient = new QueryClient();

function ProtectedLayout() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  if (!token) {
    return <Navigate replace to="/login" />;
  }
  if (isPhoneBindRequired(user)) {
    return <Navigate replace to="/bind-phone" />;
  }
  return <AppLayout />;
}

function RootRedirect() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const wechatBindTicket = useAuthStore((state) => state.wechatBindTicket);
  return <Navigate replace to={resolveLandingPath({ token, user, wechatBindTicket })} />;
}

export function AppRoot() {
  const token = useAuthStore((state) => state.token);
  const loading = useAuthStore((state) => state.loading);
  const bootstrapSession = useAuthStore((state) => state.bootstrapSession);

  useEffect(() => {
    void bootstrapSession();
  }, [token, bootstrapSession]);

  if (loading && token) {
    return (
      <div className="echo-loading-screen">
        <p>Restoring secure session...</p>
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<RootRedirect />} path="/" />
          <Route element={<LoginPage />} path="/login" />
          <Route element={<PhoneBindPage />} path="/bind-phone" />
          <Route element={<ProtectedLayout />}>
            <Route element={<HomePage />} path="/home" />
            <Route element={<DebateLobbyPage />} path="/debate" />
            <Route element={<DebateRoomPage />} path="/debate/sessions/:sessionId" />
            <Route element={<WalletPage />} path="/wallet" />
            <Route element={<OpsConsolePage />} path="/ops" />
          </Route>
          <Route element={<NotFoundPage />} path="*" />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
