import React, { useEffect, useState } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import Navbar from './Navbar';
// Import the API utilities that automatically include username
import { apiGet, getCurrentUser, isLoggedIn, validateAuth } from '../api';

type FeedbackData = {
  [section: string]: string | null;
};

const DevoFeedback: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentDateStr = searchParams.get('date') || new Date().toISOString().split('T')[0];
  const [date, setDate] = useState(currentDateStr);
  const [feedback, setFeedback] = useState<FeedbackData>({});
  const [sections, setSections] = useState<string[]>([]);
  const [userSection, setUserSection] = useState<string | null>(null);
  const [isLeaderState, setIsLeaderState] = useState<boolean>(false);
  const [isLoggedInState, setIsLoggedInState] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const navigate = useNavigate();
  const base = import.meta.env.VITE_BASE_URL || '';

  useEffect(() => {
    const initializePage = async () => {
      // Check if user is logged in using the same method as other pages
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
        localStorage.clear();
        navigate("/login");
        return;
      }

      // Now fetch the feedback data
      await fetchFeedbackData();
    };

    const fetchFeedbackData = async () => {
      try {
        const url = `/api/devos-feedback?date=${currentDateStr}`;
        console.log('Fetching devos-feedback from:', url);
        
        // Use apiGet which automatically includes username in header/params
        const res = await apiGet(url);
        
        console.log('Response status:', res.status, 'Content-Type:', res.headers.get('content-type'));
        if (!res.ok) {
          throw new Error(`Network response was not ok: ${res.status}`);
        }
        
        const text = await res.text();
        console.log('Raw devos-feedback response text:', text);
        
        let dataParsed: any;
        try {
          dataParsed = JSON.parse(text);
          // Handle double-encoded JSON string
          if (typeof dataParsed === 'string') {
            console.log('Outer JSON was a string, parsing inner JSON:', dataParsed);
            dataParsed = JSON.parse(dataParsed);
          }
        } catch (e) {
          console.error('Error parsing devos-feedback JSON:', e);
          throw e;
        }
        
        console.log('Parsed devos-feedback data:', dataParsed);
        setFeedback(dataParsed.feedback || {});
        
        // Validate that date matches YYYY-MM-DD
        const dateVal = typeof dataParsed.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dataParsed.date)
          ? dataParsed.date
          : currentDateStr;
        setDate(dateVal);
        
        // Set user state from devos-feedback payload
        if (dataParsed.user) {
          setUserSection(dataParsed.user.section);
          setIsLeaderState(dataParsed.is_leader);
          setIsLoggedInState(true);
        }
        
      } catch (error) {
        console.error('Error fetching or parsing devos-feedback:', error);
        // Fallback to default state on error
        setFeedback({});
        setDate(currentDateStr);
      } finally {
        setLoading(false);
      }
    };

    initializePage();
  }, [currentDateStr, navigate]);

  useEffect(() => {
    const fetchSections = async () => {
      try {
        // Use apiGet for sections too (though this endpoint might not need auth)
        const res = await apiGet('/api/sections');
        const data: string[] = await res.json();
        console.log('Fetched sections:', data);
        setSections(data);
      } catch (error) {
        console.error('Error fetching sections:', error);
        // Try fallback to regular fetch if apiGet fails for this endpoint
        try {
          const res = await fetch(`${base}/api/sections`);
          const data: string[] = await res.json();
          setSections(data);
        } catch (fallbackError) {
          console.error('Fallback fetch also failed:', fallbackError);
        }
      }
    };

    fetchSections();
  }, [base]);

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    setDate(newDate);
    setSearchParams({ date: newDate });
  };

  if (loading || !sections.length) {
    return (
      <>
        <Navbar />
        <div className="devo-feedback-page">
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p className="loading-text">Loading sections...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="devo-feedback-page">
        <header className="page-header">
          <div className="page-header-content">
            <h1 className="page-title">Devo's Feedback</h1>
            <p className="page-subtitle">Share your praise and prayer points from today</p>
          </div>
        </header>

        <section className="date-selector-section">
          <div className="date-selector-container">
            <label htmlFor="date-input" className="date-label">
              📅 Select Date
            </label>
            <input
              id="date-input"
              type="date"
              value={date}
              onChange={handleDateChange}
              className="date-input"
            />
          </div>
        </section>

        <section className="feedback-grid-section">
          <div className="feedback-grid">
            {sections.map(section => {
              const feedbackText = feedback[section] ?? null;
              const hasContent = Boolean(feedbackText?.trim());
              
              return (
                <div className="feedback-card" key={section}>
                  <div className="feedback-card-header">
                    <h3 className="section-title">{section}</h3>
                    {isLoggedInState && (isLeaderState || userSection === section) && (
                      <div className="action-buttons">
                        {hasContent ? (
                          <Link 
                            to={`${base}/react/devos-feedback/edit?date=${date}&section=${encodeURIComponent(section)}`} 
                            className="action-btn edit-btn"
                          >
                            ✏️ Edit
                          </Link>
                        ) : (
                          <Link 
                            to={`${base}/react/devos-feedback/edit?date=${date}&section=${encodeURIComponent(section)}`} 
                            className="action-btn add-btn"
                          >
                            ➕ Add
                          </Link>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="feedback-card-body">
                    {hasContent ? (
                      <div className="feedback-content">
                        <p className="feedback-text">{feedbackText}</p>
                      </div>
                    ) : (
                      <div className="no-feedback">
                        <div className="no-feedback-icon">💭</div>
                        <p className="no-feedback-text">No feedback submitted yet.</p>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <footer className="page-footer">
          <Link to="/" className="home-btn">
            🏠 Return to Home
          </Link>
        </footer>
      </div>

      <style>{`
        .devo-feedback-page {
          min-height: 100vh;
          background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
          padding: 2rem 1rem;
        }

        .page-header {
          text-align: center;
          margin-bottom: 2rem;
        }

        .page-header-content {
          max-width: 600px;
          margin: 0 auto;
        }

        .page-title {
          font-size: 2.5rem;
          font-weight: 700;
          color: #1e293b;
          margin-bottom: 0.5rem;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        .page-subtitle {
          font-size: 1.125rem;
          color: #64748b;
          margin: 0;
        }

        .date-selector-section {
          margin-bottom: 2rem;
          display: flex;
          justify-content: center;
        }

        .date-selector-container {
          display: flex;
          align-items: center;
          gap: 1rem;
          background: white;
          padding: 1rem 1.5rem;
          border-radius: 12px;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .date-label {
          font-weight: 500;
          color: #374151;
          font-size: 1rem;
        }

        .date-input {
          padding: 0.5rem 0.75rem;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          font-size: 1rem;
          transition: border-color 0.2s ease;
        }

        .date-input:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .feedback-grid-section {
          max-width: 1200px;
          margin: 0 auto;
        }

        .feedback-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
          gap: 1.5rem;
        }

        .feedback-card {
          background: white;
          border-radius: 16px;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
          overflow: hidden;
          transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .feedback-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 8px 12px -1px rgba(0, 0, 0, 0.15);
        }

        .feedback-card-header {
          padding: 1.5rem 1.5rem 1rem;
          border-bottom: 1px solid #f1f5f9;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .section-title {
          font-size: 1.25rem;
          font-weight: 600;
          color: #1e293b;
          margin: 0;
        }

        .action-buttons {
          display: flex;
          gap: 0.5rem;
        }

        .action-btn {
          padding: 0.5rem 0.875rem;
          border-radius: 8px;
          text-decoration: none;
          font-size: 0.875rem;
          font-weight: 500;
          transition: all 0.2s ease;
        }

        .edit-btn {
          background-color: #f59e0b;
          color: white;
        }

        .edit-btn:hover {
          background-color: #d97706;
        }

        .add-btn {
          background-color: #10b981;
          color: white;
        }

        .add-btn:hover {
          background-color: #059669;
        }

        .feedback-card-body {
          padding: 1.5rem;
        }

        .feedback-content {
          /* Styling for when feedback exists */
        }

        .feedback-text {
          color: #374151;
          line-height: 1.6;
          margin: 0;
          white-space: pre-wrap;
        }

        .no-feedback {
          text-align: center;
          padding: 2rem 1rem;
        }

        .no-feedback-icon {
          font-size: 2rem;
          margin-bottom: 0.5rem;
        }

        .no-feedback-text {
          color: #9ca3af;
          font-style: italic;
          margin: 0;
        }

        .page-footer {
          text-align: center;
          margin-top: 3rem;
        }

        .home-btn {
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.75rem 1.5rem;
          background-color: #3b82f6;
          color: white;
          text-decoration: none;
          border-radius: 12px;
          font-weight: 500;
          transition: background-color 0.2s ease;
        }

        .home-btn:hover {
          background-color: #2563eb;
        }

        .loading-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem;
        }

        .loading-spinner {
          width: 32px;
          height: 32px;
          border: 3px solid #f3f4f6;
          border-top: 3px solid #3b82f6;
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        .loading-text {
          margin-top: 1rem;
          color: #6b7280;
          font-size: 1rem;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        @media (max-width: 768px) {
          .devo-feedback-page {
            padding: 1rem 0.5rem;
          }

          .page-title {
            font-size: 2rem;
          }

          .feedback-grid {
            grid-template-columns: 1fr;
            gap: 1rem;
          }

          .date-selector-container {
            flex-direction: column;
            gap: 0.75rem;
            padding: 1rem;
          }

          .feedback-card-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 0.75rem;
          }

          .action-buttons {
            align-self: stretch;
            justify-content: flex-end;
          }
        }
      `}</style>
    </>
  );
};

export default DevoFeedback;