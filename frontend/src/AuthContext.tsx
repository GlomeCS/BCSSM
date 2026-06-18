import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  AuthUser,
  getCurrentUser,
  isLoggedIn,
  validateAuth,
  logout as apiLogout,
  LS_CURRENT_USER,
  LS_IS_LOGGED_IN,
  LS_USER_ROLE,
  LS_USER_SECTION,
  LS_CAN_EDIT_ALL,
} from "../api";

function writeAuthStorage(user: AuthUser) {
  localStorage.setItem(LS_CURRENT_USER, user.user_name);
  localStorage.setItem(LS_IS_LOGGED_IN, "true");
  if (user.role) localStorage.setItem(LS_USER_ROLE, user.role);
  else localStorage.removeItem(LS_USER_ROLE);
  if (user.section) localStorage.setItem(LS_USER_SECTION, user.section);
  else localStorage.removeItem(LS_USER_SECTION);
  localStorage.setItem(LS_CAN_EDIT_ALL, user.can_edit_all ? "true" : "false");
}

function clearAuthStorage() {
  localStorage.removeItem(LS_CURRENT_USER);
  localStorage.removeItem(LS_IS_LOGGED_IN);
  localStorage.removeItem(LS_USER_ROLE);
  localStorage.removeItem(LS_USER_SECTION);
  localStorage.removeItem(LS_CAN_EDIT_ALL);
}

type AuthState = {
  currentUser: string | null;
  userRole: string | null;
  userSection: string | null;
  canEditAll: boolean;
  loading: boolean;
};

type AuthContextValue = AuthState & {
  refresh: () => Promise<void>;
  setUser: (user: AuthUser) => void;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    currentUser: null,
    userRole: null,
    userSection: null,
    canEditAll: false,
    loading: true,
  });

  const setUser = useCallback((user: AuthUser) => {
    writeAuthStorage(user);
    setState({
      currentUser: user.user_name,
      userRole: user.role,
      userSection: user.section,
      canEditAll: user.can_edit_all,
      loading: false,
    });
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } finally {
      clearAuthStorage();
      setState({ currentUser: null, userRole: null, userSection: null, canEditAll: false, loading: false });
    }
  }, []);

  const refresh = useCallback(async () => {
    const wasLoggedIn = isLoggedIn();
    let user: AuthUser | null;
    try {
      user = await validateAuth();
    } catch {
      // Transient network error — fall back to localStorage
      if (!isLoggedIn() || !getCurrentUser()) {
        setState({ currentUser: null, userRole: null, userSection: null, canEditAll: false, loading: false });
        return;
      }
      setState({
        currentUser: getCurrentUser(),
        userRole: localStorage.getItem(LS_USER_ROLE),
        userSection: localStorage.getItem(LS_USER_SECTION),
        canEditAll: localStorage.getItem(LS_CAN_EDIT_ALL) === "true",
        loading: false,
      });
      return;
    }

    if (!user) {
      clearAuthStorage();
      setState({ currentUser: null, userRole: null, userSection: null, canEditAll: false, loading: false });
      return;
    }

    // Cross-tab race: another tab may have logged out (cleared storage) while
    // this validateAuth request was in flight. Respect that over a server
    // response that was already stale by the time it arrived.
    if (wasLoggedIn && !isLoggedIn()) {
      setState({ currentUser: null, userRole: null, userSection: null, canEditAll: false, loading: false });
      return;
    }

    writeAuthStorage(user);
    setState({
      currentUser: user.user_name,
      userRole: user.role,
      userSection: user.section,
      canEditAll: user.can_edit_all,
      loading: false,
    });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ ...state, refresh, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
