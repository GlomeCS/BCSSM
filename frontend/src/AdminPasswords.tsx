import { useState, useEffect } from "react";
import { apiGet, apiPost } from "../api";
import "./AdminPasswords.css";

interface UserPasswordStatus {
  name: string;
  has_password: boolean;
}

function AdminPasswords() {
  // null = still checking, true = confirmed Admin session, false = use secret form
  const [sessionIsAdmin, setSessionIsAdmin] = useState<boolean | null>(null);

  const [adminSecret, setAdminSecret] = useState("");
  const [users, setUsers] = useState<UserPasswordStatus[] | null>(null);
  const [selectedUser, setSelectedUser] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loadError, setLoadError] = useState("");
  const [setError, setSetError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSetting, setIsSetting] = useState(false);

  // On mount: validate the server session before trusting localStorage
  useEffect(() => {
    const localRole = localStorage.getItem("user_role");
    if (localRole !== "Admin") {
      setSessionIsAdmin(false);
      return;
    }
    // Verify the session is still live before relying on it
    apiGet("/api/admin/passwords-status")
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          setSessionIsAdmin(true);
          setUsers(data.users);
        } else {
          // Session gone or role changed — fall back to the secret form
          setSessionIsAdmin(false);
        }
      })
      .catch(() => setSessionIsAdmin(false));
  }, []);

  const extraHeaders = (secret: string): Record<string, string> =>
    sessionIsAdmin ? {} : { "X-Admin-Secret": secret };

  const fetchUsers = async (secret: string) => {
    setIsLoading(true);
    setLoadError("");
    setSuccessMessage("");
    try {
      const response = await apiGet("/api/admin/passwords-status", {
        headers: extraHeaders(secret),
      });
      if (response.status === 403) {
        setLoadError("Unauthorized. Check your admin secret.");
        return;
      }
      if (!response.ok) {
        setLoadError("Failed to load users.");
        return;
      }
      const data = await response.json();
      setUsers(data.users);
    } catch {
      setLoadError("Network error. Is the server running?");
    } finally {
      setIsLoading(false);
    }
  };

  const loadUsers = () => {
    if (!sessionIsAdmin && !adminSecret) {
      setLoadError("Admin secret is required.");
      return;
    }
    fetchUsers(adminSecret);
  };

  const handleSetPassword = async () => {
    if (!selectedUser || !newPassword) {
      setSetError("Select a user and enter a password.");
      return;
    }
    if (newPassword.length < 8) {
      setSetError("Password must be at least 8 characters.");
      return;
    }
    setIsSetting(true);
    setSetError("");
    setSuccessMessage("");
    try {
      const response = await apiPost(
        "/api/admin/set-password",
        { user_name: selectedUser, password: newPassword },
        { headers: extraHeaders(adminSecret) }
      );
      if (response.status === 403) {
        setSetError("Unauthorized. Check your admin secret.");
        return;
      }
      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setSetError((data as { error?: string }).error || "Failed to set password.");
        return;
      }
      const savedUser = selectedUser;
      setNewPassword("");
      setSelectedUser("");
      await fetchUsers(adminSecret);
      setSuccessMessage(`Password set for ${savedUser}.`);
    } catch {
      setSetError("Network error. Is the server running?");
    } finally {
      setIsSetting(false);
    }
  };

  if (sessionIsAdmin === null) {
    return (
      <div className="admin-page">
        <div className="admin-container">
          <div className="admin-body">
            <p className="admin-loading">Verifying session…</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-page">
      <div className="admin-container">
        <div className="admin-header">
          <h1 className="admin-title">Password Manager</h1>
          <p className="admin-subtitle">Set passwords for users</p>
        </div>

        <div className="admin-body">
          {/* Secret + Load — only shown when not using an Admin session */}
          {!sessionIsAdmin && (
            <div className="admin-section">
              <label className="admin-label">Admin Secret</label>
              <div className="admin-row">
                <input
                  className="admin-input"
                  type="password"
                  value={adminSecret}
                  onChange={(e) => setAdminSecret(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadUsers()}
                  placeholder="Enter ADMIN_SECRET"
                />
                <button
                  className="admin-btn admin-btn-secondary"
                  onClick={loadUsers}
                  disabled={isLoading}
                >
                  {isLoading ? "Loading..." : "Load Users"}
                </button>
              </div>
              {loadError && <p className="admin-error">{loadError}</p>}
            </div>
          )}

          {/* User status list */}
          {users !== null && (
            <>
              <div className="admin-section">
                <label className="admin-label">User Status</label>
                <ul className="admin-user-list">
                  {users.map((u) => (
                    <li key={u.name} className="admin-user-item">
                      <span className="admin-user-name">{u.name}</span>
                      <span className={`admin-badge ${u.has_password ? "badge-ok" : "badge-missing"}`}>
                        {u.has_password ? "Password set" : "No password"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Set password form */}
              <div className="admin-section">
                <label className="admin-label">Set Password</label>
                <select
                  className="admin-select"
                  value={selectedUser}
                  onChange={(e) => { setSelectedUser(e.target.value); setSetError(""); }}
                >
                  <option value="">Select user...</option>
                  {users.map((u) => (
                    <option key={u.name} value={u.name}>{u.name}</option>
                  ))}
                </select>
                <input
                  className="admin-input"
                  type="password"
                  value={newPassword}
                  onChange={(e) => { setNewPassword(e.target.value); setSetError(""); }}
                  onKeyDown={(e) => e.key === "Enter" && handleSetPassword()}
                  placeholder="New password (min 8 characters)"
                />
                {setError && <p className="admin-error">{setError}</p>}
                {successMessage && <p className="admin-success">{successMessage}</p>}
                <button
                  className="admin-btn admin-btn-primary"
                  onClick={handleSetPassword}
                  disabled={isSetting || !selectedUser || !newPassword}
                >
                  {isSetting ? "Saving..." : "Set Password"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminPasswords;
