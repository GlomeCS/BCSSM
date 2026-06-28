import React, { useState, FormEvent } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import Navbar from './Navbar';
import { apiPost } from '../api';
import { useRequireAuth } from './hooks/useRequireAuth';
import { useAuth } from './AuthContext';
import { useApiGet } from './hooks/useApiGet';
import "./DevoFeedbackEdit.css";

const DevoFeedbackEdit: React.FC = () => {
  const [searchParams] = useSearchParams();
  const dateStr = searchParams.get('date') || '';
  const section = searchParams.get('section') || '';
  const navigate = useNavigate();

  const { currentUser, loading: authLoading } = useRequireAuth();
  const { canEditAll, userSection } = useAuth();
  const canEdit = canEditAll || userSection === section;
  const [saving, setSaving] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const missingParams = !dateStr || !section;

  const { data: loadedFeedback, loading: dataLoading, error: loadError } = useApiGet<string>(
    `/api/devos-feedback?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`,
    {
      skip: !currentUser || missingParams,
      transform: (raw) => (raw as { feedback?: Record<string, string> }).feedback?.[section] ?? '',
    }
  );

  const [feedback, setFeedback] = useState<string>('');
  const [characterCount, setCharacterCount] = useState<number>(0);

  // Sync feedback state from loaded data
  React.useEffect(() => {
    if (loadedFeedback !== null) {
      setFeedback(loadedFeedback);
      setCharacterCount(loadedFeedback.length);
    }
  }, [loadedFeedback]);

  const error = missingParams ? 'Missing date or section parameters' : loadError ?? submitError;

  const MAX_CHARS = 256;

  const handleFeedbackChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setFeedback(value);
    setCharacterCount(value.length);
    if (submitError) setSubmitError(null);
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    if (!feedback.trim()) {
      setSubmitError('Please enter some feedback before saving');
      return;
    }

    if (feedback.length > MAX_CHARS) {
      setSubmitError(`Feedback must be ${MAX_CHARS} characters or fewer`);
      return;
    }

    setSaving(true);
    setSubmitError(null);

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
      setSubmitError((err as Error).message);
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

  if (!authLoading && currentUser && !canEdit) {
    navigate(`/react/devos-feedback?date=${encodeURIComponent(dateStr)}`, { replace: true });
    return null;
  }

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
                  <span className={characterCount >= MAX_CHARS ? 'at-limit' : characterCount >= MAX_CHARS * 0.85 ? 'warning' : ''}>
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
