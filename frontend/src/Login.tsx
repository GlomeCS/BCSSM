import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, login } from "../api";
import { useAuth } from "./AuthContext";
import "./Login.css";

function Login() {
  const { currentUser, loading, setUser } = useAuth();
  const [users, setUsers] = useState<string[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [password, setPassword] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
  const [error, setError] = useState<string>("");
  const comboboxRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  const filteredUsers = users.filter((u) =>
    u.toLowerCase().includes(searchQuery.toLowerCase())
  );

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (comboboxRef.current && !comboboxRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
        if (!selectedUser) setSearchQuery("");
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [selectedUser]);

  useEffect(() => {
    if (loading) return;

    if (currentUser) {
      navigate("/");
      return;
    }

    setIsLoadingUsers(true);
    apiGet("/get-users")
      .then((response) => response.json())
      .then((data: { users: string[] }) => {
        setUsers(data.users || []);
        setError("");
      })
      .catch(() => {
        setError("Failed to load users. Please refresh the page.");
      })
      .finally(() => {
        setIsLoadingUsers(false);
      });
  }, [navigate, currentUser, loading]);

  const handleLogin = async () => {
    if (!selectedUser) {
      setError("Please select a user!");
      return;
    }
    if (!password) {
      setError("Please enter your password.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const response = await login(selectedUser, password);

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();

      setUser({
        user_name: data.user_name ?? selectedUser,
        role: data.role ?? null,
        section: data.section ?? null,
        can_edit_all: !!data.can_edit_all,
      });

      navigate("/");
    } catch {
      setError("Failed to select user. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        {/* Header Section */}
        <div className="login-header">
          <div className="login-header-content">
            <h1 className="login-title">Welcome Back</h1>
            <p className="login-subtitle">Select your profile to continue</p>
          </div>
        </div>

        {/* Main Login Form */}
        <div className="login-form">
          {error && (
            <div className="error-message">
              <span className="error-icon">⚠️</span>
              <span className="error-text">{error}</span>
            </div>
          )}

          <div className="form-group">
            <label className="form-label">
              <span className="label-icon">👤</span>
              Choose User
            </label>

            {isLoadingUsers ? (
              <div className="loading-container">
                <div className="loading-spinner"></div>
                <span className="loading-text">Loading users...</span>
              </div>
            ) : (
              <div className="select-container" ref={comboboxRef}>
                <input
                  role="combobox"
                  aria-expanded={isDropdownOpen}
                  aria-haspopup="listbox"
                  className="user-select"
                  type="text"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setSelectedUser("");
                    setPassword("");
                    setError("");
                    setIsDropdownOpen(true);
                  }}
                  onFocus={() => setIsDropdownOpen(true)}
                  placeholder="Search for your profile..."
                  disabled={isLoading}
                  autoComplete="off"
                />
                <div className="select-arrow">
                  <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
                    <path d="M1 1L6 6L11 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
                {isDropdownOpen && filteredUsers.length > 0 && (
                  <ul role="listbox" className="user-dropdown">
                    {filteredUsers.map((user) => (
                      <li
                        key={user}
                        role="option"
                        aria-selected={selectedUser === user}
                        className={`user-dropdown-item${selectedUser === user ? " selected" : ""}`}
                        onMouseDown={(e) => {
                          e.preventDefault();
                          setSelectedUser(user);
                          setSearchQuery(user);
                          setPassword("");
                          setError("");
                          setIsDropdownOpen(false);
                        }}
                      >
                        {user}
                      </li>
                    ))}
                  </ul>
                )}
                {isDropdownOpen && searchQuery && filteredUsers.length === 0 && (
                  <ul role="listbox" className="user-dropdown">
                    <li className="user-dropdown-empty">No matching users</li>
                  </ul>
                )}
              </div>
            )}
          </div>

          {selectedUser && (
            <div className="form-group">
              <label className="form-label">
                <span className="label-icon">🔒</span>
                Password
              </label>
              <input
                className="password-input"
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  setError("");
                }}
                onKeyDown={(e) => e.key === "Enter" && handleLogin()}
                placeholder="Enter your password"
                disabled={isLoading}
                autoFocus
              />
            </div>
          )}

          <div className="form-actions">
            <button
              className="login-btn"
              onClick={handleLogin}
              disabled={!selectedUser || !password || isLoading || isLoadingUsers}
            >
              {isLoading ? (
                <>
                  <div className="button-spinner"></div>
                  Signing in...
                </>
              ) : (
                <>
                  <span>Continue</span>
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M1 8H15M15 8L8 1M15 8L8 15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Footer */}
        <div className="login-footer">
          <p className="footer-text">
            This system is protected by copyright and trademark laws under the laws of the United Kingdom. Unauthorized use is prohibited.
          </p>
        </div>
      </div>
    </div>
  );
}

export default Login;
