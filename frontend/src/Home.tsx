import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "./Navbar";
import { apiGet, getCurrentUser, isLoggedIn, validateAuth } from "../api";

function Home() {
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(null);
  const [dutyMessage, setDutyMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const navigate = useNavigate();

  // Check if user has access to forms based on their role
  const hasFormsAccess = (role: string | null): boolean => {
    if (!role) return false;
    const allowedRoles = ["Section Leader", "Team Leader", "Admin"];
    return allowedRoles.includes(role);
  };

  useEffect(() => {
    const initializeApp = async () => {
      console.log("Home component initializing...");
      
      // Check if user is logged in
      if (!isLoggedIn()) {
        console.log("No user logged in, redirecting to login");
        navigate("/login");
        return;
      }
      
      const user = getCurrentUser();
      console.log("Current user from localStorage:", user);
      
      if (!user) {
        navigate("/login");
        return;
      }
      
      // Validate that the user is still valid
      const isValid = await validateAuth();
      if (!isValid) {
        console.log("User validation failed, redirecting to login");
        localStorage.clear(); // Clear all auth data
        navigate("/login");
        return;
      }
      
      setCurrentUser(user);
      
      // Get user role from localStorage (updated by validateAuth)
      const role = localStorage.getItem("user_role");
      setUserRole(role);
      
      // Fetch duty info using the new API utility
      try {
        console.log("Fetching duty info...");
        const response = await apiGet("/duty-teams");
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log("Duty data received:", data);
        
        if (data && data.user) {
          setDutyMessage(data.duty_message);
          setUserRole(data.role || role); // Use API role or fallback to localStorage
        }
      } catch (error) {
        console.error("Error fetching duty info:", error);
        // Don't redirect on duty fetch error - user is still valid
      } finally {
        setLoading(false);
      }
    };

    initializeApp();
  }, [navigate]);

  if (loading) {
    return (
      <div className="home-page">
        <div style={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center', 
          height: '100vh',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          <div className="loading-spinner" style={{
            width: '40px',
            height: '40px',
            border: '4px solid #f3f3f3',
            borderTop: '4px solid #3498db',
            borderRadius: '50%',
            animation: 'spin 2s linear infinite'
          }}></div>
          <p>Loading your dashboard...</p>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      </div>
    );
  }

  return (
    <div className="home-page">
      <Navbar />
      <header className="hero">
        <div className="hero-content">
          <h1>Welcome to Ballyholme CSSM 2025</h1>
        </div>
      </header>
      <section className="info-section">
        {currentUser && (
          <p className="user-info">
            Good mae <strong>{currentUser}</strong>
          </p>
        )}
        <div className="duty-card">
          {dutyMessage ? (
            <p>Your duty today is {dutyMessage}</p>
          ) : (
            <p>No duty assigned today.</p>
          )}
        </div>
        
        {/* Forms access for Section Leaders, Team Leaders, and Admins */}
        {hasFormsAccess(userRole) && (
          <div 
            className="forms-section"
            style={{
              marginTop: '2.5rem',
              padding: '2rem',
              background: 'linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)',
              borderRadius: '16px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)'
            }}
          >
            <h3 
              style={{
                fontSize: '1.5rem',
                fontWeight: '600',
                color: '#1e293b',
                marginBottom: '1.25rem',
                letterSpacing: '-0.025em',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
              }}
            >
              Receipts & Expenses
            </h3>
            <div style={{ marginTop: '1rem' }}>
              <a 
                href="https://forms.gle/c6gaUmwMMBEATmbc8" 
                target="_blank" 
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  padding: '0.875rem 1.5rem',
                  backgroundColor: '#3b82f6',
                  color: 'white',
                  textDecoration: 'none',
                  borderRadius: '12px',
                  fontSize: '1rem',
                  fontWeight: '500',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                  letterSpacing: '-0.01em',
                  transition: 'all 0.2s ease-in-out',
                  boxShadow: '0 2px 4px -1px rgba(59, 130, 246, 0.3)',
                  border: 'none',
                  cursor: 'pointer'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#2563eb';
                  e.currentTarget.style.transform = 'translateY(-1px)';
                  e.currentTarget.style.boxShadow = '0 4px 8px -1px rgba(59, 130, 246, 0.4)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#3b82f6';
                  e.currentTarget.style.transform = 'translateY(0)';
                  e.currentTarget.style.boxShadow = '0 2px 4px -1px rgba(59, 130, 246, 0.3)';
                }}
              >
                <span style={{ marginRight: '0.5rem' }}>📋</span>
                Submit Receipt
              </a>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

export default Home;