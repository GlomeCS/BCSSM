import React, { useState, useEffect, FormEvent } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Navbar from './Navbar';
import { apiGet, apiPost } from '../api';
import { useRequireAuth } from './hooks/useRequireAuth';
import "./DevoFeedbackEdit.css";

const DevoFeedbackEdit: React.FC = () => {
  const [searchParams] = useSearchParams();
  const dateStr = searchParams.get('date') || '';
  const section = searchParams.get('section') || '';
  const navigate = useNavigate();

  const { currentUser, loading: authLoading } = useRequireAuth();
  const [feedback, setFeedback] = useState<string>('');
  const [dataLoading, setDataLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [characterCount, setCharacterCount] = useState<number>(0);

  useEffect(() => {
    if (!currentUser) return;
    setDataLoading(true);
    setError(null);
    setFeedback('');
    setCharacterCount(0);

    if (!dateStr || !section) {
      setError('Missing date or section parameters');
      setDataLoading(false);
      return;
    }

    const controller = new AbortController();

    const loadFeedback = async () => {
      try {
        const res = await apiGet(
          `/api/devos-feedback?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`,
          { signal: controller.signal }
        );
        if (!res.ok) throw new Error(`Failed to load feedback: ${res.statusText}`);

        const data = await res.json();
        console.log('Fetched feedback response:', data);

        const existingFeedback = data.feedback?.[section] ?? '';
        setFeedback(existingFeedback);
        setCharacterCount(existingFeedback.length);
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        console.error('Error loading feedback:', err);
        setError((err as Error).message);
      } finally {
        if (!controller.signal.aborted) setDataLoading(false);
      }
    };

    loadFeedback();
    return () => controller.abort();
  }, [currentUser, dateStr, section]);

  const MAX_CHARS = 140;

  const handleFeedbackChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setFeedback(value);
    setCharacterCount(value.length);
    if (error) setError(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!feedback.trim()) {
      setError('Please enter some feedback before saving');
      return;
    }

    if (feedback.length > MAX_CHARS) {
      setError(`Feedback must be ${MAX_CHARS} characters or fewer`);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const res = await apiPost(
        `/api/devos-feedback/edit?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`,
        { feedback }
      );

      if (!res.ok) {
        throw new Error(`Failed to save feedback: ${res.statusText}`);
      }

      navigate(`/react/devos-feedback?date=${encodeURIComponent(dateStr)}`, { replace: true });
    } catch (err) {
      console.error('Error saving feedback:', err);
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    navigate(`/react/devos-feedback?date=${encodeURIComponent(dateStr)}`);
  };

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

  if (authLoading || dataLoading) {
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
                  rows={6}
                  required
                  maxLength={MAX_CHARS}
                  value={feedback}
                  onChange={handleFeedbackChange}
                  placeholder={`Share your praise and prayer points about the ${section}' day on ${formatDate(dateStr)}...`}
                  disabled={saving}
                />
                <div className="character-counter">
                  <span className={characterCount >= MAX_CHARS ? 'at-limit' : characterCount > MAX_CHARS * 0.85 ? 'warning' : ''}>
                    {characterCount} / {MAX_CHARS}
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
                disabled={saving || !feedback.trim() || characterCount > MAX_CHARS}
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
