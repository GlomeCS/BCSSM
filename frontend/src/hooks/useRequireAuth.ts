import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export function useRequireAuth(): { currentUser: string | null; loading: boolean } {
  const { currentUser, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !currentUser) {
      navigate("/login");
    }
  }, [loading, currentUser, navigate]);

  return { currentUser, loading };
}
