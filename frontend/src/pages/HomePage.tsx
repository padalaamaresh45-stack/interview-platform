import { useAuth } from "../hooks/useAuth";

export function HomePage() {
  const { user } = useAuth();
  return (
    <main>
      <h1>Welcome, {user?.full_name}</h1>
      <p>Logged in as {user?.email} ({user?.role}).</p>
    </main>
  );
}
