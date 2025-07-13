import React, { useState, useEffect, FormEvent } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Navbar from './Navbar';
// Import the API utilities that automatically include username
import { apiGet, apiPost, getCurrentUser, isLoggedIn, validateAuth } from '../api';

const DevoFeedbackEdit: React.FC = () => {
  const [searchParams] = useSearchParams();
  const dateStr = searchParams.get('date') || '';
  const section = searchParams.get('section') || '';
  const navigate = useNavigate();

  const [feedback, setFeedback] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [characterCount, setCharacterCount] = useState<number>(0);

  // Load existing feedback
  useEffect(() => {
    const initializePage = async () => {
      if (!dateStr || !section) {
        setError('Missing date or section parameters');
        setLoading(false);
        return;
      }

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

      // Now load the feedback data
      await loadFeedback();
    };
    
    const loadFeedback = async () => {
      try {
        // Use apiGet which automatically includes username in header/params
        const res = await apiGet(
          `/api/devos-feedback?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`
        );
        if (!res.ok) throw new Error(`Failed to load feedback: ${res.statusText}`);
        
        const data = await res.json();
        console.log('Fetched feedback response:', data);
        
        // Populate the textarea with the specific section's feedback string
        const existingFeedback = data.feedback?.[section] ?? '';
        setFeedback(existingFeedback);
        setCharacterCount(existingFeedback.length);
      } catch (err) {
        console.error('Error loading feedback:', err);
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    initializePage();
  }, [dateStr, section, navigate]);

  // Handle textarea changes
  const handleFeedbackChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setFeedback(value);
    setCharacterCount(value.length);
    // Clear error when user starts typing
    if (error) setError(null);
  };

  // Submit handler
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    
    if (!feedback.trim()) {
      setError('Please enter some feedback before saving');
      return;
    }

    setSaving(true);
    setError(null);
    
    try {
      // Use apiPost which automatically includes username in header/body
      const res = await apiPost(
        `/api/devos-feedback/edit?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`,
        { feedback }
      );
      
      if (!res.ok) {
        throw new Error(`Failed to save feedback: ${res.statusText}`);
      }
      
      // Navigate back to the feedback page
      navigate(`/react/devos-feedback?date=${encodeURIComponent(dateStr)}`, { replace: true });
    } catch (err) {
      console.error('Error saving feedback:', err);
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  // Cancel handler
  const handleCancel = () => {
    navigate(`/react/devos-feedback?date=${encodeURIComponent(dateStr)}`);
  };

  // Format date for display
  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleDateString('en-GB', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="edit-feedback-page">
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p className="loading-text">Loading feedback...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="edit-feedback-page">
        <header className="edit-header">
          <div className="edit-header-content">
            <h1 className="edit-title">
              ✏️ Edit Feedback
            </h1>
            <div className="edit-info">
              <div className="edit-info-item">
                <span className="info-label">Section:</span>
                <span className="info-value">{section}</span>
              </div>
              <div className="edit-info-item">
                <span className="info-label">Date:</span>
                <span className="info-value">{formatDate(dateStr)}</span>
              </div>
            </div>
          </div>
        </header>

        <main className="edit-main">
          {error && (
            <div className="error-message">
              <div className="error-icon">⚠️</div>
              <div className="error-text">{error}</div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="feedback-form">
            <div className="form-group">
              <label htmlFor="feedbackArea" className="form-label">
                💬 Your Feedback
              </label>
              <div className="textarea-container">
                <textarea
                  id="feedbackArea"
                  className="feedback-textarea"
                  rows={12}
                  required
                  value={feedback}
                  onChange={handleFeedbackChange}
                  placeholder={`Share your praise and prayer points about the ${section}' day on ${formatDate(dateStr)}...`}
                  disabled={saving}
                />
                <div className="character-counter">
                  <span className={characterCount > 1000 ? 'warning' : ''}>
                    {characterCount.toLocaleString()} characters
                  </span>
                </div>
              </div>
            </div>

            <div className="form-actions">
              <button
                type="button"
                className="cancel-btn"
                onClick={handleCancel}
                disabled={saving}
              >
                ❌ Cancel
              </button>
              <button 
                type="submit" 
                className="save-btn"
                disabled={saving || !feedback.trim()}
              >
                {saving ? (
                  <>
                    <div className="button-spinner"></div>
                    Saving...
                  </>
                ) : (
                  <>💾 Save Feedback</>
                )}
              </button>
            </div>
          </form>
        </main>
      </div>

      <style>{`
        .edit-feedback-page {
          min-height: 100vh;
          background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
          padding: 2rem 1rem;
        }

        .edit-header {
          text-align: center;
          margin-bottom: 2rem;
        }

        .edit-header-content {
          max-width: 600px;
          margin: 0 auto;
        }

        .edit-title {
          font-size: 2.25rem;
          font-weight: 700;
          color: #1e293b;
          margin-bottom: 1rem;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        .edit-info {
          display: flex;
          justify-content: center;
          gap: 2rem;
          flex-wrap: wrap;
        }

        .edit-info-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 0.25rem;
        }

        .info-label {
          font-size: 0.875rem;
          color: #64748b;
          font-weight: 500;
        }

        .info-value {
          font-size: 1rem;
          color: #1e293b;
          font-weight: 600;
          padding: 0.25rem 0.75rem;
          background: white;
          border-radius: 8px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }

        .edit-main {
          max-width: 800px;
          margin: 0 auto;
        }

        .error-message {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 12px;
          padding: 1rem 1.25rem;
          margin-bottom: 1.5rem;
        }

        .error-icon {
          font-size: 1.25rem;
        }

        .error-text {
          color: #dc2626;
          font-weight: 500;
        }

        .feedback-form {
          background: white;
          border-radius: 16px;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
          padding: 2rem;
        }

        .form-group {
          margin-bottom: 1.5rem;
        }

        .form-label {
          display: block;
          font-size: 1.125rem;
          font-weight: 600;
          color: #374151;
          margin-bottom: 0.75rem;
        }

        .textarea-container {
          position: relative;
        }

        .feedback-textarea {
          width: 100%;
          padding: 1rem;
          border: 2px solid #e5e7eb;
          border-radius: 12px;
          font-size: 1rem;
          line-height: 1.6;
          resize: vertical;
          min-height: 200px;
          transition: border-color 0.2s ease;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }

        .feedback-textarea:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }

        .feedback-textarea:disabled {
          background-color: #f9fafb;
          cursor: not-allowed;
        }

        .character-counter {
          position: absolute;
          bottom: 0.75rem;
          right: 0.75rem;
          font-size: 0.875rem;
          color: #6b7280;
          background: rgba(255, 255, 255, 0.9);
          padding: 0.25rem 0.5rem;
          border-radius: 6px;
        }

        .character-counter .warning {
          color: #dc2626;
          font-weight: 600;
        }

        .form-actions {
          display: flex;
          gap: 1rem;
          justify-content: flex-end;
          margin-top: 2rem;
        }

        .cancel-btn, .save-btn {
          padding: 0.75rem 1.5rem;
          border: none;
          border-radius: 12px;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .cancel-btn {
          background-color: #f3f4f6;
          color: #374151;
        }

        .cancel-btn:hover:not(:disabled) {
          background-color: #e5e7eb;
        }

        .save-btn {
          background-color: #3b82f6;
          color: white;
        }

        .save-btn:hover:not(:disabled) {
          background-color: #2563eb;
        }

        .cancel-btn:disabled, .save-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .button-spinner {
          width: 16px;
          height: 16px;
          border: 2px solid transparent;
          border-top: 2px solid currentColor;
          border-radius: 50%;
          animation: spin 1s linear infinite;
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
          .edit-feedback-page {
            padding: 1rem 0.5rem;
          }

          .edit-title {
            font-size: 1.875rem;
          }

          .edit-info {
            gap: 1rem;
          }

          .feedback-form {
            padding: 1.5rem;
          }

          .form-actions {
            flex-direction: column-reverse;
          }

          .cancel-btn, .save-btn {
            width: 100%;
            justify-content: center;
          }
        }
      `}</style>
    </>
  );
};

export default DevoFeedbackEdit;