import { useEffect, useState, type FormEvent } from "react";
import {
  createUser,
  deactivateUser,
  listUsers,
  reactivateUser,
  resetPassword,
  updateUserName,
  type AdminUser,
} from "../api/users";

export function UserListPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newFullName, setNewFullName] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "interviewer">("interviewer");
  const [creating, setCreating] = useState(false);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editingName, setEditingName] = useState("");

  async function refresh() {
    setLoading(true);
    try {
      setUsers(await listUsers());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      await createUser(newEmail, newPassword, newFullName, newRole);
      setNewEmail("");
      setNewPassword("");
      setNewFullName("");
      setNewRole("interviewer");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setCreating(false);
    }
  }

  async function handleSaveName(id: number) {
    try {
      await updateUserName(id, editingName);
      setEditingId(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleToggleActive(user: AdminUser) {
    try {
      if (user.is_active) {
        await deactivateUser(user.id);
      } else {
        await reactivateUser(user.id);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  async function handleResetPassword(user: AdminUser) {
    const newPasswordValue = window.prompt(`New password for ${user.email}`);
    if (!newPasswordValue) return;
    try {
      await resetPassword(user.id, newPasswordValue);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    }
  }

  return (
    <main>
      <h1>Users</h1>
      {error && <p role="alert">{error}</p>}

      <form onSubmit={handleCreate}>
        <label htmlFor="new-user-email">Email</label>
        <input
          id="new-user-email"
          type="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          required
        />
        <label htmlFor="new-user-password">Initial password</label>
        <input
          id="new-user-password"
          type="password"
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
          required
        />
        <label htmlFor="new-user-full-name">Full name</label>
        <input
          id="new-user-full-name"
          value={newFullName}
          onChange={(e) => setNewFullName(e.target.value)}
          required
        />
        <label htmlFor="new-user-role">Role</label>
        <select id="new-user-role" value={newRole} onChange={(e) => setNewRole(e.target.value as "admin" | "interviewer")}>
          <option value="interviewer">Interviewer</option>
          <option value="admin">Admin</option>
        </select>
        <button type="submit" disabled={creating}>
          {creating ? "Creating…" : "Create user"}
        </button>
      </form>

      {loading ? (
        <p>Loading…</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>
                  {editingId === user.id ? (
                    <>
                      <input value={editingName} onChange={(e) => setEditingName(e.target.value)} />
                      <button onClick={() => handleSaveName(user.id)}>Save</button>
                      <button onClick={() => setEditingId(null)}>Cancel</button>
                    </>
                  ) : (
                    <>
                      {user.full_name}{" "}
                      <button
                        onClick={() => {
                          setEditingId(user.id);
                          setEditingName(user.full_name);
                        }}
                      >
                        Edit
                      </button>
                    </>
                  )}
                </td>
                <td>{user.email}</td>
                <td>{user.role}</td>
                <td>{user.is_active ? "Active" : "Deactivated"}</td>
                <td>
                  <button onClick={() => handleToggleActive(user)}>
                    {user.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                  <button onClick={() => handleResetPassword(user)}>Reset password</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
