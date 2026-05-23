import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { isLoggedIn, getCurrentUser, validateAuth } from "../../api";

export function useRequireAuth(): { currentUser: string | null; loading: boolean } {
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const check = async () => {
      try {
        if (!isLoggedIn() || !getCurrentUser()) {
          navigate("/login");
          setLoading(false);
          return;
        }
        const isValid = await validateAuth();
        if (!isValid) {
          localStorage.clear();
          navigate("/login");
          setLoading(false);
          return;
        }
        setCurrentUser(getCurrentUser());
        setLoading(false);
      } catch (error) {
        // Network/transport error: don't clear the session — the server may be
        // temporarily unavailable. Keep the user logged in so they aren't forced
        // out during a transient outage.
        console.error("Auth check failed (transient):", error);
        setCurrentUser(getCurrentUser());
        setLoading(false);
      }
    };
    check();
  }, [navigate]);

  return { currentUser, loading };
}
