import React, { useState, useEffect, FormEvent } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const DevoFeedbackEdit: React.FC = () => {
  const [searchParams] = useSearchParams();
  const dateStr = searchParams.get('date') || '';
  const section = searchParams.get('section') || '';
  const navigate = useNavigate();

  const [feedback, setFeedback] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Load existing feedback
  useEffect(() => {
    if (!dateStr || !section) {
      setError('Missing date or section');
      setLoading(false);
      return;
    }
    (async () => {
      try {
        const res = await fetch(
          `/api/devos-feedback?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`
        );
        if (!res.ok) throw new Error(res.statusText);
        const data = await res.json();
        console.log('Fetched feedback response:', data);
        console.log('Type of data.feedback:', typeof data.feedback, data.feedback);
        // Populate the textarea with the specific section's feedback string
        setFeedback(data.feedback?.[section] ?? '');
      } catch (err) {
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    })();
  }, [dateStr, section]);

  // Submit handler
  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(
        `/api/devos-feedback/edit?date=${encodeURIComponent(dateStr)}&section=${encodeURIComponent(section)}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ feedback }),
        }
      );
      if (!res.ok) throw new Error(res.statusText);
      navigate(`/react/devos-feedback?date=${encodeURIComponent(dateStr)}`, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="container mt-5 pt-5 text-center">
        <p>Loading feedback…</p>
      </div>
    );
  }

  return (
    <div className="container mt-5 pt-5">
      <h1 className="mb-4 text-center">
        Edit Feedback for {section} on {dateStr}
      </h1>
      {error && <div className="alert alert-danger">{error}</div>}
      <form onSubmit={handleSubmit}>
        <div className="mb-3">
          <label htmlFor="feedbackArea" className="form-label">
            Feedback:
          </label>
          <textarea
            id="feedbackArea"
            className="form-control"
            rows={10}
            required
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </div>
        <div className="d-flex justify-content-end">
          <button
            type="button"
            className="btn btn-secondary me-2"
            onClick={() => navigate(`/react/devos-feedback?date=${encodeURIComponent(dateStr)}`)}
            disabled={saving}
          >
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default DevoFeedbackEdit;