import type { ReactNode } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

function BoardIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16M15 4v16" />
    </svg>
  );
}

function BriefcaseIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  );
}

function PeopleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="9" cy="8" r="3.2" />
      <path d="M2.5 20c0-3.6 2.9-6.2 6.5-6.2S15.5 16.4 15.5 20" />
      <circle cx="17.5" cy="8.5" r="2.6" />
      <path d="M15.7 13.9c2.9.4 4.8 2.8 4.8 6.1" />
    </svg>
  );
}

function TeamIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="8" r="3.3" />
      <path d="M4 20c0-4.4 3.6-7 8-7s8 2.6 8 7" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="M16 17l5-5-5-5M21 12H9" />
    </svg>
  );
}

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
}

export function AuthenticatedShell() {
  const { user, initializing, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (initializing) {
    return <p>Loading…</p>;
  }

  if (user === null) {
    return <Navigate to="/login" replace />;
  }

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  const adminNav: NavItem[] = [
    { to: "/", label: "Pipeline board", icon: <BoardIcon /> },
    { to: "/positions", label: "Positions", icon: <BriefcaseIcon /> },
    { to: "/candidates", label: "Candidates", icon: <PeopleIcon /> },
    { to: "/users", label: "Users", icon: <TeamIcon /> },
    { to: "/calendar", label: "Calendar", icon: <CalendarIcon /> },
  ];
  const interviewerNav: NavItem[] = [
    { to: "/my-candidates", label: "My Candidates", icon: <PeopleIcon /> },
    { to: "/calendar", label: "Calendar", icon: <CalendarIcon /> },
  ];
  const navItems = user.role === "admin" ? adminNav : interviewerNav;

  function isActive(to: string) {
    return to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);
  }

  return (
    <div className="app-shell">
      <nav className="nav-rail">
        <div className="nav-rail-items">
          {navItems.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              aria-label={item.label}
              title={item.label}
              className={`nav-rail-item${isActive(item.to) ? " active" : ""}`}
            >
              {item.icon}
            </Link>
          ))}
        </div>
        <div className="nav-rail-items">
          <span className="nav-rail-user" title={`${user.full_name} (${user.role})`}>
            {user.full_name.slice(0, 1).toUpperCase()}
          </span>
          <button className="nav-rail-item" onClick={handleLogout} aria-label="Log out" title="Log out">
            <LogoutIcon />
          </button>
        </div>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
