import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import Navbar from './Navbar';
import { apiGet } from '../api';
import { useRequireAuth } from './hooks/useRequireAuth';
import "./DevoFeedback.css";

type FeedbackData = {
  [section: string]: string | null;
};

type DevoFeedbackResponse = {
  feedback?: FeedbackData;
  date?: string;
  user?: { section: string };
  is_leader?: boolean;
};

const DevoFeedback: React.FC = () => {
  const { currentUser, loading: authLoading } = useRequireAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const currentDateStr = searchParams.get('date') || new Date().toISOString().split('T')[0];
  const [date, setDate] = useState(currentDateStr);
  const [feedback, setFeedback] = useState<FeedbackData>({});
  const [sections, setSections] = useState<string[]>([]);
  const [userSection, setUserSection] = useState<string | null>(null);
  const [isLeaderState, setIsLeaderState] = useState<boolean>(false);
  const [dataLoading, setDataLoading] = useState<boolean>(true);
  const [sectionsLoading, setSectionsLoading] = useState<boolean>(true);
  const [splitPickerOpen, setSplitPickerOpen] = useState(false);
  const splitPickerRef = useRef<HTMLDivElement>(null);
  const base = import.meta.env.VITE_BASE_URL || '';

  const sectionParam = searchParams.get('section') ?? '';
  const focusedSections = sectionParam
    ? Array.from(new Set(sectionParam.split(',').map(s => s.trim()).filter(Boolean)))
    : [];
  const windowSize = focusedSections.length;
  const anchorIndex = windowSize > 0 ? sections.indexOf(focusedSections[0]) : -1;

  const enterFocus = (section: string) => {
    setSearchParams({ date, section });
  };

  const exitFocus = () => {
    setSearchParams({ date });
  };

  const navigatePrev = () => {
    if (sections.length === 0 || windowSize === 0) return;
    setSplitPickerOpen(false);
    const newAnchor = anchorIndex <= 0 ? sections.length - 1 : anchorIndex - 1;
    const newSections = Array.from({ length: windowSize }, (_, i) =>
      sections[(newAnchor + i) % sections.length]
    );
    setSearchParams({ date, section: newSections.join(',') });
  };

  const navigateNext = () => {
    if (sections.length === 0 || windowSize === 0) return;
    setSplitPickerOpen(false);
    const newAnchor = anchorIndex < 0 || anchorIndex >= sections.length - 1 ? 0 : anchorIndex + 1;
    const newSections = Array.from({ length: windowSize }, (_, i) =>
      sections[(newAnchor + i) % sections.length]
    );
    setSearchParams({ date, section: newSections.join(',') });
  };

  const availableSections = sections.filter(s => !focusedSections.includes(s));

  const addSplit = (section: string) => {
    setSearchParams({ date, section: [...focusedSections, section].join(',') });
    setSplitPickerOpen(false);
  };

  const canEdit = (section: string) =>
    currentUser !== null && (isLeaderState || userSection === section);

  useEffect(() => {
    if (windowSize === 0) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (splitPickerOpen) {
          setSplitPickerOpen(false);
        } else {
          setSearchParams({ date });
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [windowSize, date, setSearchParams, splitPickerOpen]);

  useEffect(() => {
    if (!splitPickerOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (splitPickerRef.current && !splitPickerRef.current.contains(e.target as Node)) {
        setSplitPickerOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [splitPickerOpen]);

  useEffect(() => {
    if (!currentUser) return;
    setDataLoading(true);
    setFeedback({});
    setUserSection(null);
    setIsLeaderState(false);

    const fetchFeedbackData = async () => {
      try {
        const url = `/api/devos-feedback?date=${currentDateStr}`;
        console.log('Fetching devos-feedback from:', url);

        const res = await apiGet(url);

        console.log('Response status:', res.status, 'Content-Type:', res.headers.get('content-type'));
        if (!res.ok) {
          throw new Error(`Network response was not ok: ${res.status}`);
        }

        const text = await res.text();
        console.log('Raw devos-feedback response text:', text);

        let dataParsed: DevoFeedbackResponse;
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

        const dateVal = typeof dataParsed.date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dataParsed.date)
          ? dataParsed.date
          : currentDateStr;
        setDate(dateVal);

        if (dataParsed.user) {
          setUserSection(dataParsed.user.section);
          setIsLeaderState(dataParsed.is_leader ?? false);
        }

      } catch (error) {
        console.error('Error fetching or parsing devos-feedback:', error);
        setFeedback({});
        setDate(currentDateStr);
      } finally {
        setDataLoading(false);
      }
    };

    fetchFeedbackData();
  }, [currentUser, currentDateStr]);

  useEffect(() => {
    const fetchSections = async () => {
      const parseSections = async (res: Response): Promise<string[]> => {
        if (!res.ok) throw new Error(`Sections fetch failed: ${res.status}`);
        const data: unknown = await res.json();
        if (!Array.isArray(data) || !data.every((x) => typeof x === 'string')) {
          throw new Error('Sections response is not a string array');
        }
        return data;
      };
      try {
        const res = await apiGet('/api/sections');
        const data = await parseSections(res);
        console.log('Fetched sections:', data);
        setSections(data);
      } catch (error) {
        console.error('Error fetching sections:', error);
        try {
          const res = await apiGet('/api/sections');
          const data = await parseSections(res);
          setSections(data);
        } catch (fallbackError) {
          console.error('Fallback fetch also failed:', fallbackError);
        }
      } finally {
        setSectionsLoading(false);
      }
    };

    fetchSections();
  }, [base]);

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newDate = e.target.value;
    setDate(newDate);
    setSearchParams({ date: newDate });
  };

  if (authLoading || dataLoading || sectionsLoading) {
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

  const closeBtn = (
    <button className="focus-close-btn" onClick={exitFocus} aria-label="Close focus view">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <path d="M2 2L16 16M16 2L2 16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      </svg>
    </button>
  );

  const navBar = (
    <div className="focus-nav">
      <button className="focus-nav-btn" onClick={navigatePrev} aria-label="Previous section">‹</button>
      <span className="focus-nav-indicator">
        {anchorIndex >= 0 ? anchorIndex + 1 : '?'} / {sections.length}
      </span>
      <button className="focus-nav-btn" onClick={navigateNext} aria-label="Next section">›</button>
      {availableSections.length > 0 && windowSize < 3 && (
        <div className="focus-split-picker-wrapper" ref={splitPickerRef}>
          <button
            className={`focus-split-btn${splitPickerOpen ? ' focus-split-btn--open' : ''}`}
            onClick={() => setSplitPickerOpen(p => !p)}
            aria-label="Split view"
            aria-expanded={splitPickerOpen}
            aria-haspopup="listbox"
          >
            + Split
          </button>
          {splitPickerOpen && (
            <div className="focus-split-picker" role="listbox" aria-label="Add section to split view">
              {availableSections.map(section => (
                <button
                  key={section}
                  className="focus-split-picker-item"
                  role="option"
                  onClick={() => addSplit(section)}
                >
                  {section}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderColumnContent = (section: string) => {
    const text = feedback[section] ?? null;
    const hasContent = Boolean(text?.trim());
    return hasContent ? (
      <p className="focus-text">{text}</p>
    ) : (
      <div className="focus-empty">
        <div className="focus-empty-icon">💭</div>
        <p className="focus-empty-text">No feedback submitted yet.</p>
      </div>
    );
  };

  return (
    <>
      <Navbar />

      {windowSize === 1 && (
        <div className="focus-overlay" role="dialog" aria-modal="true" aria-label={`${focusedSections[0]} feedback`}>
          <div className="focus-header">
            <div className="focus-header-left">
              <h2 className="focus-section-title">{focusedSections[0]}</h2>
              {canEdit(focusedSections[0]) && (
                <Link
                  to={`${base}/react/devos-feedback/edit?date=${date}&section=${encodeURIComponent(focusedSections[0])}`}
                  className={`action-btn ${feedback[focusedSections[0]]?.trim() ? 'edit-btn' : 'add-btn'}`}
                >
                  {feedback[focusedSections[0]]?.trim() ? '✏️ Edit' : '➕ Add'}
                </Link>
              )}
            </div>
            {closeBtn}
          </div>

          <div className="focus-body">
            {renderColumnContent(focusedSections[0])}
          </div>

          {navBar}
        </div>
      )}

      {windowSize > 1 && (
        <div
          className="focus-overlay focus-overlay--split"
          role="dialog"
          aria-modal="true"
          aria-label={`Comparing ${focusedSections.join(', ')}`}
        >
          <div className="focus-split-topbar">
            <span className="focus-split-breadcrumb">{focusedSections.join(' · ')}</span>
            {closeBtn}
          </div>

          <div className="focus-columns">
            {focusedSections.map((section, i) => (
              <div className={`focus-column${i < focusedSections.length - 1 ? ' focus-column--divider' : ''}`} key={section}>
                <div className="focus-column-header">
                  <h2 className="focus-section-title">{section}</h2>
                  {canEdit(section) && (
                    <Link
                      to={`${base}/react/devos-feedback/edit?date=${date}&section=${encodeURIComponent(section)}`}
                      className={`action-btn ${feedback[section]?.trim() ? 'edit-btn' : 'add-btn'}`}
                    >
                      {feedback[section]?.trim() ? '✏️ Edit' : '➕ Add'}
                    </Link>
                  )}
                </div>
                <div className="focus-column-body">
                  {renderColumnContent(section)}
                </div>
              </div>
            ))}
          </div>

          {navBar}
        </div>
      )}

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
                <div
                  className={`feedback-card${!hasContent ? ' feedback-card--empty' : ''}`}
                  key={section}
                >
                  <div className="feedback-card-header">
                    <h3 className="section-title">{section}</h3>
                    <span className="expand-icon" aria-hidden="true">⤢</span>
                    {currentUser !== null && (isLeaderState || userSection === section) && (
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
                  <div
                    className="feedback-card-body"
                    onClick={() => enterFocus(section)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); enterFocus(section); } }}
                    aria-label={`View ${section} feedback in focus mode`}
                  >
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
