import { useState, useEffect } from "react";
import Navbar from "./Navbar";
import { apiGet } from "../api";
import { useRequireAuth } from "./hooks/useRequireAuth";
import "./Home.css";

function Home() {
  const { currentUser, loading: authLoading } = useRequireAuth();
  const [userRole, setUserRole] = useState<string | null>(null);
  const [dutyMessage, setDutyMessage] = useState<string | null>(null);
  const [dataLoading, setDataLoading] = useState<boolean>(true);

  // Check if user has access to forms based on their role
  const hasFormsAccess = (role: string | null): boolean => {
    if (!role) return false;
    const allowedRoles = ["Section Leader", "Team Leader", "Admin"];
    return allowedRoles.includes(role);
  };

  useEffect(() => {
    if (!currentUser) return;

    const fetchDutyInfo = async () => {
      const role = localStorage.getItem("user_role");
      setUserRole(role);

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
          setUserRole(data.role || role);
        }
      } catch (error) {
        console.error("Error fetching duty info:", error);
      } finally {
        setDataLoading(false);
      }
    };

    fetchDutyInfo();
  }, [currentUser]);

  if (authLoading || dataLoading) {
    return (
      <>
        <Navbar />
        <div className="home-page">
          <div className="home-loading">
            <div className="loading-spinner"></div>
            <p>Loading your dashboard...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="home-page">
      <header className="hero">
        <div className="hero-content">
          <h1>Welcome to Ballyholme CSSM 2026</h1>
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
          <div className="forms-section">
            <h3>Receipts & Expenses</h3>
            <div className="forms-section-links">
              <a
                href="https://forms.gle/c6gaUmwMMBEATmbc8"
                target="_blank"
                rel="noopener noreferrer"
                className="receipt-link"
              >
                <span>📋</span>
                Submit Receipt
              </a>
            </div>
          </div>
        )}

        {/* Bank Details for non-Section Leaders */}
        {!hasFormsAccess(userRole) && (
          <div className="bank-details-section">
            <h3>Ballyholme CSSM Bank Account</h3>
            <div className="bank-details-card">
              <div className="bank-details-grid">
                <div className="bank-field">
                  <label>Account Name</label>
                  <div className="bank-field-value">Scripture Union Northern Ireland</div>
                </div>
                <div className="bank-field">
                  <label>Sort Code</label>
                  <div className="bank-field-value">98-00-30</div>
                </div>
                <div className="bank-field">
                  <label>Account Number</label>
                  <div className="bank-field-value">05391716</div>
                </div>
                <div className="bank-field">
                  <label>Bank Name</label>
                  <div className="bank-field-value">Ulster Bank</div>
                </div>
              </div>
              <div className="bank-note">
                <strong>Note:</strong> Please include your name and "Team Fees" in the payment reference when making transfers e.g. "Ross Team Fees" or "Harrison TF"
              </div>
            </div>
          </div>
        )}
      </section>
      </div>
    </>
  );
}

export default Home;
