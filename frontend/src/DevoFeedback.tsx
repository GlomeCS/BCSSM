import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import Navbar from './Navbar';

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
  const [isLeader, setIsLeader] = useState<boolean>(false);
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const base = import.meta.env.VITE_BASE_URL || '';

  useEffect(() => {
    const url = `${base}/api/devos-feedback?date=${currentDateStr}`;
    console.log('Fetching devos-feedback from:', url);
    fetch(url)
      .then(res => {
        console.log('Response status:', res.status, 'Content-Type:', res.headers.get('content-type'));
        if (!res.ok) {
          throw new Error(`Network response was not ok: ${res.status}`);
        }
        return res.text();
      })
      .then(text => {
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
        setUserSection(dataParsed.user.section);
        setIsLeader(dataParsed.is_leader);
        setIsLoggedIn(true);
      })
      .catch(error => {
        console.error('Error fetching or parsing devos-feedback:', error);
        // Fallback to default state on error
        setFeedback({});
        setDate(currentDateStr);
      });
  }, [currentDateStr]);

  useEffect(() => {
    fetch(`${base}/api/sections`)
      .then(res => res.json())
      .then((data: string[]) => {
        console.log('Fetched sections:', data);
        setSections(data);
      })
      .catch(console.error);
  }, []);

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    setDate(newDate);
    setSearchParams({ date: newDate });
  };

  if (!sections.length) {
    return (
      <div className="container mt-5 pt-5 text-center">
        <p>Loading sections…</p>
      </div>
    );
  }

  return (
    <>
      <Navbar />
      <div className="container mt-4 pt-5">
        <div className="text-center mb-4">
          <h1>Devo's Feedback</h1>
        </div>
        <div className="d-flex justify-content-center mb-4">
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

        <div className="row row-cols-1 row-cols-md-2 g-4 justify-content-center">
          {sections.map(section => {
            const feedbackText = feedback[section] ?? null;
            return (
              <div className="col" key={section}>
                <div className="card h-100">
                  <div className="card-header d-flex justify-content-between align-items-center">
                    <strong>{section}</strong>
                    {isLoggedIn && (isLeader || userSection === section) && (
                      feedbackText ? (
                        <Link to={`${base}/react/devos-feedback/edit?date=${date}&section=${encodeURIComponent(section)}`} className="btn btn-sm btn-primary">
                          Edit
                        </Link>
                      ) : (
                        <Link to={`${base}/react/devos-feedback/edit?date=${date}&section=${encodeURIComponent(section)}`} className="btn btn-sm btn-success">
                          Add
                        </Link>
                      )
                    )}
                  </div>
                  <div className="card-body">
                    {feedbackText ? (
                      <p className="card-text" style={{ whiteSpace: 'pre-wrap' }}>
                        {feedbackText}
                      </p>
                    ) : (
                      <p className="text-muted fst-italic">No feedback submitted yet.</p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="mt-4 text-center">
          <Link to="/" className="btn btn-secondary">Return to Home</Link>
        </div>
      </div>
    </>
  );
};

export default DevoFeedback;