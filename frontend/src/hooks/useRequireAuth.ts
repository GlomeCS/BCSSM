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
      } catch {
        localStorage.clear();
        navigate("/login");
        setLoading(false);
      }
    };
    check();
  }, [navigate]);

  return { currentUser, loading };
}
