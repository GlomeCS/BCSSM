import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import Navbar from './Navbar';

type FeedbackData = {
  [section: string]: string | null;
};

const DevoFeedback: React.FC = () => {
  const [feedback, setFeedback] = useState<FeedbackData>({});
  const [date, setDate] = useState('');
  const [searchParams, setSearchParams] = useSearchParams();
  const currentDateStr = searchParams.get('date') || new Date().toISOString().split('T')[0];

  useEffect(() => {
    fetch(`/api/devos-feedback?date=${currentDateStr}`)
      .then(res => res.json())
      .then(data => {
        setFeedback(data.feedback || {});
        setDate(data.date || currentDateStr);
      });
  }, [currentDateStr]);

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchParams({ date: e.target.value });
  };

  return (
    <>
      <Navbar />
      <div className="container mt-4">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h1 className="text-center flex-grow-1">Devo's Feedback</h1>
          <form method="GET" className="d-flex align-items-center">
            <input
              type="date"
              value={date}
              onChange={handleDateChange}
              className="form-control me-2"
              style={{ maxWidth: '200px' }}
            />
          </form>
        </div>

        <div className="row row-cols-1 row-cols-md-2 g-4">
          {Object.entries(feedback).map(([section, feedbackText]) => (
            <div className="col" key={section}>
              <div className="card h-100">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <strong>{section}</strong>
                  {feedbackText ? (
                    <Link to={`/devos-feedback/edit?date=${date}&section=${section}`} className="btn btn-sm btn-primary">Edit</Link>
                  ) : (
                    <Link to={`/devos-feedback/edit?date=${date}&section=${section}`} className="btn btn-sm btn-success">Add</Link>
                  )}
                </div>
                <div className="card-body">
                  {feedbackText ? (
                    <p className="card-text" style={{ whiteSpace: 'pre-wrap' }}>{feedbackText}</p>
                  ) : (
                    <p className="text-muted fst-italic">No feedback submitted yet.</p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 text-center">
          <Link to="/" className="btn btn-secondary">Return to Home</Link>
        </div>
      </div>
    </>
  );
};

export default DevoFeedback;