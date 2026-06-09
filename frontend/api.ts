// utils/api.ts

export const getCurrentUser = (): string | null => {
    return localStorage.getItem("currentUser");
  };
  
  export const isLoggedIn = (): boolean => {
    return localStorage.getItem("is_logged_in") === "true" && !!getCurrentUser();
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
      localStorage.removeItem('currentUser');
      localStorage.removeItem('is_logged_in');
      localStorage.removeItem('user_role');
      localStorage.removeItem('user_section');
      localStorage.removeItem('can_edit_all');
    }
  };

  // Auth validation function.
  // Returns true if the server confirms the session is valid.
  // Returns false if the server explicitly says the session is invalid.
  // Throws on network/transport errors so callers can distinguish transient failures.
  export const validateAuth = async (): Promise<boolean> => {
    const currentUser = getCurrentUser();

    if (!currentUser) {
      return false;
    }

    const response = await apiGet('/api/auth/validate');
    if (!response.ok) {
      // 400 = no session / not authenticated; 401/403 = explicitly rejected.
      // All three mean "not logged in" — return false rather than throwing.
      if (response.status === 400 || response.status === 401 || response.status === 403) return false;
      throw new Error(`Auth check failed with status ${response.status}`);
    }
    const data = await response.json();

    if (data.is_valid) {
      localStorage.setItem("is_logged_in", "true");
      if (data.user_name) localStorage.setItem("currentUser", data.user_name);
      if (data.role) localStorage.setItem("user_role", data.role);
      if (data.section) localStorage.setItem("user_section", data.section);
      localStorage.setItem("can_edit_all", data.can_edit_all ? "true" : "false");
      return true;
    }

    return false;
  };