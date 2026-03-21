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
    </>
  );
};

export default DevoFeedback;