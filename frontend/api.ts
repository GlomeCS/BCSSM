// utils/api.ts

export const LS_CURRENT_USER = "currentUser";
export const LS_IS_LOGGED_IN = "is_logged_in";
export const LS_USER_ROLE = "user_role";
export const LS_USER_SECTION = "user_section";
export const LS_CAN_EDIT_ALL = "can_edit_all";

export type AuthUser = {
  user_name: string;
  role: string | null;
  section: string | null;
  can_edit_all: boolean;
};

export const getCurrentUser = (): string | null => {
    return localStorage.getItem(LS_CURRENT_USER);
  };

  export const isLoggedIn = (): boolean => {
    return localStorage.getItem(LS_IS_LOGGED_IN) === "true" && !!getCurrentUser();
  };
  
  export const apiCall = async (
    url: string,
    options: RequestInit = {}
  ): Promise<Response> => {
    const headers = new Headers(options.headers);
    return fetch(url, {
      ...options,
      credentials: 'include',
      headers,
    });
  };
  
  // Wrapper functions for common HTTP methods
  export const apiGet = (url: string, options: RequestInit = {}) => {
    return apiCall(url, { ...options, method: 'GET' });
  };
  
  export const apiPost = (url: string, data: Record<string, unknown> = {}, options: RequestInit = {}) => {
    return apiCall(url, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      body: JSON.stringify(data)
    });
  };
  
  export const login = (userName: string, password: string): Promise<Response> => {
    return apiPost('/api/auth/login', { user_name: userName, password });
  };

  export const logout = async (): Promise<void> => {
    try {
      await apiPost('/api/auth/logout', {});
    } finally {
      localStorage.removeItem(LS_CURRENT_USER);
      localStorage.removeItem(LS_IS_LOGGED_IN);
      localStorage.removeItem(LS_USER_ROLE);
      localStorage.removeItem(LS_USER_SECTION);
      localStorage.removeItem(LS_CAN_EDIT_ALL);
    }
  };

  // Auth validation function.
  // Returns true if the server confirms the session is valid.
  // Returns false if the server explicitly says the session is invalid.
  // Throws on network/transport errors so callers can distinguish transient failures.
  export const validateAuth = async (): Promise<boolean> => {
    const response = await apiGet('/api/auth/validate');
    if (!response.ok) {
      // 400 = no session / not authenticated; 401/403 = explicitly rejected.
      // All three mean "not logged in" — return false rather than throwing.
      if (response.status === 400 || response.status === 401 || response.status === 403) return false;
      throw new Error(`Auth check failed with status ${response.status}`);
    }
    const data = await response.json();

    if (data.is_valid) {
      localStorage.setItem(LS_IS_LOGGED_IN, "true");
      if (data.user_name) localStorage.setItem(LS_CURRENT_USER, data.user_name);
      if (data.role) localStorage.setItem(LS_USER_ROLE, data.role);
      if (data.section) localStorage.setItem(LS_USER_SECTION, data.section);
      localStorage.setItem(LS_CAN_EDIT_ALL, data.can_edit_all ? "true" : "false");
      return true;
    }

    return false;
  };