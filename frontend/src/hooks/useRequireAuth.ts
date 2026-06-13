import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export function useRequireAuth(): { currentUser: string | null; loading: boolean } {
  const { currentUser, loading } = useAuth();
  const navigate = useNavigate();
  const redirecting = !loading && !currentUser;

  useEffect(() => {
    if (redirecting) {
      navigate("/login");
    }
  }, [redirecting, navigate]);

  return { currentUser, loading: loading || redirecting };
}
