import React, { useState, useEffect, FormEvent } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Navbar from './Navbar';

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
    if (!dateStr || !section) {
      setError('Missing date or section parameters');
      setLoading(false);
      return;
    }
    
    const loadFeedback = async () => {
      try {
        const res = await fetch(
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

    loadFeedback();
  }, [dateStr, section]);

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
      const res = await fetch(
        `/api/devos-feedback/edit?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feedback }),
        }
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
                  placeholder={`Share your praise and prayer points about ${section}'s devotion on ${formatDate(dateStr)}...`}
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
    </>
  );
};

export default DevoFeedbackEdit;