// utils/api.ts

export const getCurrentUser = (): string | null => {
    return localStorage.getItem("currentUser");
  };
  
  export const isLoggedIn = (): boolean => {
    return localStorage.getItem("is_logged_in") === "true" && !!getCurrentUser();
  };
  
  // Enhanced fetch that automatically includes username
  export const apiCall = async (
    url: string, 
    options: RequestInit = {}
  ): Promise<Response> => {
    const currentUser = getCurrentUser();
    
    // Prepare headers
    const headers = new Headers(options.headers);
    
    // Add current user to headers for all requests
    if (currentUser) {
      headers.set('X-Current-User', currentUser);
    }
    
    // For POST requests, include username in body if it's JSON
    let body = options.body;
    if (options.method === 'POST' && currentUser) {
      // If there's existing JSON body, parse and add username
      if (headers.get('Content-Type')?.includes('application/json')) {
        try {
          const existingData = body ? JSON.parse(body as string) : {};
          body = JSON.stringify({
            ...existingData,
            user_name: currentUser
          });
        } catch {
          // If not valid JSON, create new JSON body with username
          body = JSON.stringify({ user_name: currentUser });
          headers.set('Content-Type', 'application/json');
        }
      }
    }
    
    // For GET requests, add username as query parameter
    if ((!options.method || options.method === 'GET') && currentUser && !url.includes('user_name=')) {
      const separator = url.includes('?') ? '&' : '?';
      url = `${url}${separator}user_name=${encodeURIComponent(currentUser)}`;
    }
    
    return fetch(url, {
      ...options,
      headers,
      body
    });
  };
  
  // Wrapper functions for common HTTP methods
  export const apiGet = (url: string, options: RequestInit = {}) => {
    return apiCall(url, { ...options, method: 'GET' });
  };
  
  export const apiPost = (url: string, data: Record<string, unknown> = {}, options: RequestInit = {}) => {
    const currentUser = getCurrentUser();
    const bodyData = currentUser ? { ...data, user_name: currentUser } : data;
    
    return apiCall(url, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      body: JSON.stringify(bodyData)
    });
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
      if (response.status === 401 || response.status === 403) return false;
      throw new Error(`Auth check failed with status ${response.status}`);
    }
    const data = await response.json();

    if (data.is_valid) {
      localStorage.setItem("is_logged_in", "true");
      if (data.role) localStorage.setItem("user_role", data.role);
      if (data.section) localStorage.setItem("user_section", data.section);
      localStorage.setItem("is_leader", data.is_leader ? "true" : "false");
      return true;
    }

    return false;
  };