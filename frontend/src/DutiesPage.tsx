import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "./Navbar";
// Import the API utilities that automatically include username
import { apiGet, getCurrentUser, isLoggedIn, validateAuth } from "../api";

type Duty = {
  id: string;
  name: string;
  description: string;
  members: { name: string; week: string }[];
  isCurrentUser: boolean;
  teamName?: string;
};

type ApiDuty = {
  id: string;
  name: string;
  duty_description: string;
  members: { name: string; week: string }[];
  is_current_user: boolean;
  team_name?: string;
};

type ScheduleDay = {
  date: string;
  day_name: string;
  week: string;
  duties: {
    duty_name: string;
    duty_description: string;
    team_name: string;
    team_members: { name: string; week: string }[];
  }[];
};

type ScheduleData = {
  schedule: ScheduleDay[];
};

export default function DutiesPage() {
  const [duties, setDuties] = useState<Duty[]>([]);
  const [schedule, setSchedule] = useState<ScheduleDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [scheduleLoading, setScheduleLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'today' | 'schedule'>('today');
  const navigate = useNavigate();

  useEffect(() => {
    const initializePage = async () => {
      // Check if user is logged in using the same method as Home page
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

      // Now fetch the duties data using API utilities
      await Promise.all([fetchDuties(), fetchSchedule()]);
    };

    const fetchDuties = async () => {
      try {
        // Use apiGet which automatically includes username in header/params
        const res = await apiGet("/api/duties/today");
        if (!res.ok) throw new Error(`Failed to fetch duties: ${res.statusText}`);
        
        const data = await res.json() as ApiDuty[];
        console.log("Raw duties from API:", data);
        
        const mapped: Duty[] = data.map((d) => ({
          id: d.id,
          name: d.name,
          description: d.duty_description,
          members: d.members,
          isCurrentUser: d.is_current_user,
          teamName: d.team_name,
        }));
        
        console.log("Mapped duties for UI:", mapped);
        setDuties(mapped);
      } catch (err) {
        console.error("Error fetching duties:", err);
        setError((err as Error).message);
      } finally {
        setLoading(false);
      }
    };

    const fetchSchedule = async () => {
      try {
        // Use apiGet which automatically includes username in header/params
        const res = await apiGet("/api/duties/schedule");
        if (!res.ok) throw new Error(`Failed to fetch schedule: ${res.statusText}`);
        
        const data: ScheduleData = await res.json();
        console.log("Raw schedule from API:", data);
        
        setSchedule(data.schedule || []);
      } catch (err) {
        console.error("Error fetching schedule:", err);
        setError((err as Error).message);
      } finally {
        setScheduleLoading(false);
      }
    };

    initializePage();
  }, [navigate]);

  // Extract team number from team name (format: "Duty Team 1", "Duty Team 2", etc.)
  const getTeamNumber = (teamName?: string): string => {
    console.log('getTeamNumber called with:', teamName);
    if (!teamName) {
      console.log('No team name provided');
      return '';
    }
    const match = teamName.match(/Duty Team (\d+)/i);
    console.log('Regex match result:', match);
    const result = match ? match[1] : '';
    console.log('Extracted team number:', result);
    return result;
  };

  // Get current date for display
  const getCurrentDate = () => {
    return new Date().toLocaleDateString('en-GB', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  // Format date for schedule display
  const formatScheduleDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-GB', {
      weekday: 'short',
      month: 'short',
      day: 'numeric'
    });
  };

  if (loading && scheduleLoading) {
    return (
      <>
        <Navbar />
        <div className="duties-page">
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p className="loading-text">Loading duties...</p>
          </div>
        </div>
      </>
    );
  }

  const myDuties = duties.filter((d) => d.isCurrentUser);
  const otherDuties = duties.filter((d) => !d.isCurrentUser);

  return (
    <>
      <Navbar />
      <div className="duties-page">
        <header className="duties-header">
          <div className="duties-header-content">
            <h1 className="duties-title">📋 Duties Dashboard</h1>
            <p className="duties-date">{getCurrentDate()}</p>
          </div>
          
          {/* Tab Navigation */}
          <div className="tab-navigation">
            <button 
              className={`tab-button ${activeTab === 'today' ? 'active' : ''}`}
              onClick={() => setActiveTab('today')}
            >
              📅 Today's Duties
            </button>
            <button 
              className={`tab-button ${activeTab === 'schedule' ? 'active' : ''}`}
              onClick={() => setActiveTab('schedule')}
            >
              🗓️ 2-Week Schedule
            </button>
          </div>
        </header>

        {error && (
          <div className="error-message">
            <div className="error-icon">⚠️</div>
            <div className="error-text">
              Failed to load data: {error}
            </div>
          </div>
        )}

        <main className="duties-main">
          {activeTab === 'today' && (
            <>
              {/* Your Duties Section */}
              <section className="duties-section your-duties">
                <h2 className="section-title">
                  <span className="section-icon">👤</span>
                  Your Duties
                </h2>
                
                {myDuties.length > 0 ? (
                  <div className="duties-grid">
                    {myDuties.map((duty) => {
                      console.log('Processing my duty:', duty);
                      const teamNumber = getTeamNumber(duty.teamName);
                      console.log('Team number for my duty:', teamNumber);
                      return (
                        <div key={duty.id} className="duty-card your-duty-card">
                          <div className="duty-card-header">
                            <h3 className="duty-name">{duty.name}</h3>
                            <div className="duty-badge your-duty-badge">
                              {teamNumber ? `Team ${teamNumber} Duty` : 'Your Duty'}
                            </div>
                          </div>
                          <div className="duty-card-body">
                            <p className="duty-description">{duty.description}</p>
                            {duty.members.length > 0 && (
                              <div className="duty-members">
                                <div className="members-label">👥 Team Members:</div>
                                <div className="members-list-compact">
                                  {duty.members.map((member, index) => (
                                    <span key={index} className="member-tag">
                                      <span className="member-name">{member.name}</span>
                                      <span className="member-week">{member.week}</span>
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="no-duties-message">
                    <div className="no-duties-icon">🎉</div>
                    <h3 className="no-duties-title">No Duty Today!</h3>
                    <p className="no-duties-text">
                      Enjoy your day off from duties. You can still check what others are doing below.
                    </p>
                  </div>
                )}
              </section>

              {/* Other Duties Section */}
              <section className="duties-section other-duties">
                <h2 className="section-title">
                  <span className="section-icon">👥</span>
                  Other Duties
                </h2>
                
                {otherDuties.length > 0 ? (
                  <div className="duties-grid">
                    {otherDuties.map((duty) => {
                      console.log('Processing other duty:', duty);
                      const teamNumber = getTeamNumber(duty.teamName);
                      console.log('Team number for other duty:', teamNumber);
                      return (
                        <div key={duty.id} className="duty-card other-duty-card">
                          <div className="duty-card-header">
                            <h3 className="duty-name">{duty.name}</h3>
                            <div className="duty-badge other-duty-badge">
                              {teamNumber ? `Team ${teamNumber} Duty` : 'Team Duty'}
                            </div>
                          </div>
                          <div className="duty-card-body">
                            <p className="duty-description">{duty.description}</p>
                            {duty.members.length > 0 && (
                              <div className="duty-members">
                                <div className="members-label">👥 Assigned to:</div>
                                <div className="members-list-compact">
                                  {duty.members.map((member, index) => (
                                    <span key={index} className="member-tag">
                                      <span className="member-name">{member.name}</span>
                                      <span className="member-week">{member.week}</span>
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="no-duties-message">
                    <div className="no-duties-icon">📭</div>
                    <h3 className="no-duties-title">No Other Duties</h3>
                    <p className="no-duties-text">
                      There are no other duties scheduled for today.
                    </p>
                  </div>
                )}
              </section>
            </>
          )}

          {activeTab === 'schedule' && (
            <section className="duties-section schedule-section">
              <h2 className="section-title">
                <span className="section-icon">🗓️</span>
                2-Week Duty Schedule (Starting July 5th, 2025)
              </h2>
              
              {scheduleLoading ? (
                <div className="loading-container">
                  <div className="loading-spinner"></div>
                  <p className="loading-text">Loading schedule...</p>
                </div>
              ) : schedule.length > 0 ? (
                (() => {
                  // Get all unique duty names for column headers
                  const allDuties = new Set<string>();
                  schedule.forEach(day => {
                    if (day.duties && Array.isArray(day.duties)) {
                      day.duties.forEach(duty => {
                        if (duty && duty.duty_name && typeof duty.duty_name === 'string') {
                          allDuties.add(duty.duty_name);
                        }
                      });
                    }
                  });
                  const sortedDuties = Array.from(allDuties).sort();

                  return (
                    <div className="schedule-table-container">
                      <table className="schedule-table">
                        <thead>
                          <tr>
                            <th className="date-column">Date & Day</th>
                            {sortedDuties.map(dutyName => (
                              <th key={dutyName} className="duty-column">{dutyName}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {schedule.map((day, index) => {
                            const dateOnly = new Date(day.date).toISOString().split("T")[0];
                            if (dateOnly === "2025-07-12") {
                              return (
                                <tr key={index}>
                                  <td colSpan={sortedDuties.length + 1}></td>
                                </tr>
                              );
                            }
                            // Create a map of duty name to team for this day
                            const dutyTeamMap: { [key: string]: string } = {};
                            if (day.duties && Array.isArray(day.duties)) {
                              day.duties.forEach(duty => {
                                if (duty && duty.duty_name && duty.team_name && 
                                    typeof duty.duty_name === 'string' && typeof duty.team_name === 'string') {
                                  dutyTeamMap[duty.duty_name] = duty.team_name;
                                }
                              });
                            }
                            
                            return (
                              <tr key={index} className="schedule-row">
                                <td className="date-cell">
                                  <div className="date-with-week">
                                    <span className="date-text">{formatScheduleDate(day.date)}</span>
                                    {(() => {
                                      const d = new Date(day.date);
                                      const dateOnly = d.toISOString().split("T")[0];
                                      if (dateOnly === "2025-07-05" || dateOnly === "2025-07-06") {
                                        return <span className="week-badge-small prep-week">Prep Week</span>;
                                      } else if (dateOnly === "2025-07-12") {
                                        return <span className="week-badge-small prep-week">FREEDOM</span>;;
                                      } else if (day.week === "Week A" || day.week === "Week B") {
                                        return (
                                          <span className={`week-badge-small ${day.week === "Week A" ? "week-a" : "week-b"}`}>
                                            {day.week}
                                          </span>
                                        );
                                      } else {
                                        return null;
                                      }
                                    })()}
                                  </div>
                                </td>
                                {sortedDuties.map(dutyName => (
                                  <td key={dutyName} className="duty-cell">
                                    {dutyTeamMap[dutyName] ? (
                                      <span className="team-number">
                                        {dutyTeamMap[dutyName].replace(/team\s*/i, '')}
                                      </span>
                                    ) : (
                                      <span className="no-duty">—</span>
                                    )}
                                  </td>
                                ))}
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  );
                })()
              ) : (
                <div className="no-duties-message">
                  <div className="no-duties-icon">📅</div>
                  <h3 className="no-duties-title">No Schedule Available</h3>
                  <p className="no-duties-text">
                    Unable to load the duty schedule at this time.
                  </p>
                </div>
              )}
            </section>
          )}
        </main>

        <footer className="duties-footer">
          <div className="footer-content">
            <p className="footer-text">
              💡 Need help with your duties? Contact your team leader or check the duty guidelines.
            </p>
          </div>
        </footer>
      </div>

      {/* All your existing styles remain the same */}
      <style>{`
        .tab-navigation {
          display: flex;
          gap: 8px;
          margin-top: 16px;
          border-bottom: 2px solid #e5e7eb;
        }

        .tab-button {
          padding: 12px 24px;
          border: none;
          background: none;
          color: #6b7280;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s ease;
          border-bottom: 3px solid transparent;
        }

        .tab-button:hover {
          color: #374151;
          background-color: #f9fafb;
        }

        .tab-button.active {
          color: #2563eb;
          border-bottom-color: #2563eb;
          background-color: #eff6ff;
        }

        .schedule-section {
          margin-top: 24px;
        }

        .schedule-table-container {
          margin-top: 16px;
          background: white;
          border-radius: 12px;
          box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
          overflow: auto;
          max-height: 70vh;
        }

        .schedule-table {
          width: 100%;
          border-collapse: collapse;
        }

        .schedule-table th {
          background: #f8fafc;
          padding: 16px 12px;
          text-align: left;
          font-weight: 600;
          color: #374151;
          border-bottom: 2px solid #e5e7eb;
          position: sticky;
          top: 0;
          z-index: 10;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }

        .schedule-table thead th::after {
          content: '';
          position: absolute;
          bottom: -1px;
          left: 0;
          right: 0;
          height: 1px;
          background: #e5e7eb;
        }

        .date-column {
          width: 15%;
        }

        .day-column {
          width: 15%;
        }

        .week-column {
          width: 15%;
        }

        .duties-column {
          width: 55%;
        }

        .schedule-row {
          border-bottom: 1px solid #f3f4f6;
          transition: background-color 0.2s ease;
        }

        .schedule-row:hover {
          background-color: #f9fafb;
        }

        .schedule-row:last-child {
          border-bottom: none;
        }

        .schedule-table td {
          padding: 12px;
          vertical-align: top;
        }

        .date-cell {
          font-weight: 500;
          color: #374151;
        }

        .day-cell {
          font-weight: 500;
          color: #1f2937;
        }

        .week-badge-small {
          padding: 3px 6px;
          border-radius: 6px;
          font-size: 11px;
          font-weight: 500;
          align-self: flex-start;
        }

        .week-badge-small.week-a {
          background-color: #dbeafe;
          color: #1d4ed8;
        }

        .week-badge-small.week-b {
          background-color: #dcfce7;
          color: #16a34a;
        }

        .week-badge-small.prep-week {
          background-color: #fef9c3; /* light yellow */
          color: #ca8a04;            /* amber-700 */
        }

        .duty-teams-list {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .duty-team-tag {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          background: #f1f5f9;
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 6px 10px;
          font-size: 14px;
          transition: background-color 0.2s ease;
        }

        .duty-team-tag:hover {
          background-color: #e2e8f0;
        }

        .duty-name {
          color: #1e293b;
          font-weight: 500;
        }

        .team-name {
          color: #64748b;
          font-size: 13px;
        }

        .no-duties-text {
          color: #9ca3af;
          font-style: italic;
          font-size: 14px;
        }

        .loading-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 48px;
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
          margin-top: 16px;
          color: #6b7280;
          font-size: 14px;
        }

        /* New compact member styles */
        .members-list-compact {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-top: 8px;
        }

        .member-tag {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: #f1f5f9;
          color: #475569;
          padding: 4px 8px;
          border-radius: 6px;
          font-size: 13px;
          font-weight: 500;
          border: 1px solid #e2e8f0;
          transition: background-color 0.2s ease;
        }

        .member-tag:hover {
          background: #e2e8f0;
        }

        .member-name {
          color: #1e293b;
        }

        .member-week {
          color: #64748b;
          font-size: 12px;
          font-weight: 400;
          padding: 2px 4px;
          background: #e2e8f0;
          border-radius: 4px;
        }

        /* Remove old member item styles */
        .member-item {
          display: none;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        @media (max-width: 768px) {
          .tab-navigation {
            flex-direction: column;
          }
          
          .tab-button {
            text-align: left;
          }

          .schedule-table-container {
            overflow-x: auto;
          }

          .schedule-table {
            min-width: 600px;
          }

          .date-column {
            width: 120px;
            min-width: 120px;
          }

          .duty-column {
            min-width: 70px;
            padding: 8px 4px;
            font-size: 12px;
          }

          .duty-cell {
            padding: 8px 4px;
          }

          .team-number {
            font-size: 12px;
            padding: 3px 6px;
            min-width: 16px;
          }

          .date-with-week {
            gap: 2px;
          }

          .date-text {
            font-size: 13px;
          }

          .week-badge-small {
            font-size: 10px;
            padding: 2px 4px;
          }


          .member-tag {
            font-size: 12px;
            padding: 3px 6px;
            gap: 4px;
          }

          .member-week {
            font-size: 11px;
            padding: 1px 3px;
          }
        }
      `}</style>
    </>
  );
}