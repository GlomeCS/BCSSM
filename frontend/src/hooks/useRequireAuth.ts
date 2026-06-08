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
        // Re-read after await: another tab may have cleared localStorage while
        // the server round-trip was in flight.
        const user = getCurrentUser();
        if (!user) {
          navigate("/login");
          setLoading(false);
          return;
        }
        setCurrentUser(user);
        setLoading(false);
      } catch (error) {
        // Network/transport error: don't clear the session — the server may be
        // temporarily unavailable. Keep the user logged in so they aren't forced
        // out during a transient outage.
        // Trade-off: stale localStorage metadata (e.g. user_role, can_edit_all) may
        // persist if the server is down for an extended period and roles change in
        // the DB during the outage. See GitHub issue #135 for tracking.
        console.error("Auth check failed (transient):", error);
        const user = getCurrentUser();
        if (!user) {
          navigate("/login");
          setLoading(false);
          return;
        }
        setCurrentUser(user);
        setLoading(false);
      }
    };
    check();
  }, [navigate]);

  return { currentUser, loading };
}
