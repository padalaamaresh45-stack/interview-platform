import { Navigate, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function AuthenticatedShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (user === null) {
    return <Navigate to="/login" replace />;
  }

  async function handleLogout() {
    await logout();
    navigate("/login");
  }

  return (
    <div>
      <header>
        <span>{user.full_name}</span> ({user.role})
        <button onClick={handleLogout}>Log out</button>
      </header>
      <Outlet />
    </div>
  );
}
