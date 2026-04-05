import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuthStore } from "@echoisle/auth-sdk";
import { Button } from "@echoisle/ui";

const NAV_ITEMS = [
  { to: "/home", label: "Home" },
  { to: "/debate", label: "Lobby" },
  { to: "/wallet", label: "Wallet" },
  { to: "/ops", label: "Ops" }
] as const;

export function AppLayout() {
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  return (
    <div className="echo-shell">
      <aside className="echo-sidebar">
        <Link className="echo-brand" to="/home">
          EchoIsle
        </Link>
        <p className="echo-brand-sub">AI Debate Judge</p>
        <nav className="echo-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              className={({ isActive }) => `echo-nav-link${isActive ? " is-active" : ""}`}
              to={item.to}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="echo-user-block">
          <strong>{user?.fullname || "Local Super Admin"}</strong>
          <span>{user?.email || user?.phoneE164 || "super@none.org"}</span>
        </div>
        <Button
          className="echo-logout-btn"
          onClick={() => {
            logout();
            navigate("/login", { replace: true });
          }}
        >
          Logout
        </Button>
      </aside>
      <main className="echo-main">
        <Outlet />
      </main>
    </div>
  );
}
