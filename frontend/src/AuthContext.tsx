import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import {
  getCurrentUser,
  isLoggedIn,
  validateAuth,
  LS_CURRENT_USER,
  LS_IS_LOGGED_IN,
  LS_USER_ROLE,
  LS_USER_SECTION,
  LS_CAN_EDIT_ALL,
} from "../api";

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

  const refresh = useCallback(async () => {
    if (!isLoggedIn() || !getCurrentUser()) {
      setState({ currentUser: null, userRole: null, userSection: null, canEditAll: false, loading: false });
      return;
    }
    try {
      const valid = await validateAuth();
      if (!valid) {
        clearAuthStorage();
        setState({ currentUser: null, userRole: null, userSection: null, canEditAll: false, loading: false });
        return;
      }
    } catch {
      // Transient network error — keep existing localStorage values
    }
    setState({
      currentUser: getCurrentUser(),
      userRole: localStorage.getItem(LS_USER_ROLE),
      userSection: localStorage.getItem(LS_USER_SECTION),
      canEditAll: localStorage.getItem(LS_CAN_EDIT_ALL) === "true",
      loading: false,
    });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <AuthContext.Provider value={{ ...state, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
