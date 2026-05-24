import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, getCurrentUser, isLoggedIn } from "../api";
import "./Login.css";

function Login() {
  const [users, setUsers] = useState<string[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingUsers, setIsLoadingUsers] = useState(true);
  const [error, setError] = useState<string>("");
  const navigate = useNavigate();

  useEffect(() => {
    // Check if user is already logged in
    if (isLoggedIn()) {
      const currentUser = getCurrentUser();
      console.log("User already logged in:", currentUser);
      navigate("/");
      return;
    }

    // Fetch available users
    setIsLoadingUsers(true);
    apiGet("/get-users")
      .then((response) => response.json())
      .then((data: { users: string[] }) => {
        console.log("Fetched users:", data.users);
        setUsers(data.users || []);
        setError("");
      })
      .catch((error) => {
        console.error("Error fetching users:", error);
        setError("Failed to load users. Please refresh the page.");
      })
      .finally(() => {
        setIsLoadingUsers(false);
      });
  }, [navigate]);

  const handleLogin = async () => {
    if (!selectedUser) {
      setError("Please select a user!");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      // Use raw fetch so the pre-existing currentUser in localStorage
      // does not get injected into the body by apiPost and overwrite selectedUser.
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: selectedUser }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      console.log("Login response:", data);

      // Store user state in localStorage for persistent auth
      localStorage.setItem("is_logged_in", "true");
      localStorage.setItem("currentUser", data.user_name ?? selectedUser);

      if (data.section) {
        localStorage.setItem("user_section", data.section);
      } else {
        localStorage.removeItem("user_section");
      }

      if (data.role) {
        localStorage.setItem("user_role", data.role);
      } else {
        localStorage.removeItem("user_role");
      }

      localStorage.setItem("is_leader", data.is_leader ? "true" : "false");

      // Navigate to home page
      console.log("Login successful, navigating to home");
      navigate("/");
    } catch (error) {
      console.error("Error selecting user:", error);
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
              <div className="select-container">
                <select
                  className="user-select"
                  value={selectedUser}
                  onChange={(e) => {
                    setSelectedUser(e.target.value);
                    setError("");
                  }}
                  disabled={isLoading}
                >
                  <option value="">Select your profile...</option>
                  {users.map((user) => (
                    <option key={user} value={user}>
                      {user}
                    </option>
                  ))}
                </select>
                <div className="select-arrow">
                  <svg width="12" height="8" viewBox="0 0 12 8" fill="none">
                    <path d="M1 1L6 6L11 1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
              </div>
            )}
          </div>

          <div className="form-actions">
            <button
              className="login-btn"
              onClick={handleLogin}
              disabled={!selectedUser || isLoading || isLoadingUsers}
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