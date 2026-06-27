import { useState } from "react";
import Navbar from "./Navbar";
import { useRequireAuth } from "./hooks/useRequireAuth";
import { useApiGet } from "./hooks/useApiGet";
import "./DutiesPage.css";

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
  duty_order: { [duty_name: string]: number };
};

function mapApiDuties(raw: unknown): Duty[] {
  return (raw as ApiDuty[]).map((d) => ({
    id: d.id,
    name: d.name,
    description: d.duty_description,
    members: d.members,
    isCurrentUser: d.is_current_user,
    teamName: d.team_name,
  }));
}

type ScheduleResult = { days: ScheduleDay[]; dutyOrder: { [name: string]: number } };

function mapSchedule(raw: unknown): ScheduleResult {
  const data = raw as ScheduleData;
  return {
    days: data.schedule || [],
    dutyOrder: data.duty_order || {},
  };
}

export default function DutiesPage() {
  const { currentUser, loading: authLoading } = useRequireAuth();
  const [activeTab, setActiveTab] = useState<'today' | 'schedule'>('today');
  const [week1Open, setWeek1Open] = useState(true);
  const [week2Open, setWeek2Open] = useState(true);

  const { data: duties, loading, error } = useApiGet<Duty[]>(
    "/api/duties/today",
    { skip: !currentUser, transform: mapApiDuties }
  );
  const { data: scheduleResult, loading: scheduleLoading } = useApiGet<ScheduleResult>(
    "/api/duties/schedule",
    { skip: !currentUser, transform: mapSchedule }
  );
  const schedule = scheduleResult?.days ?? [];
  const dutyOrder = scheduleResult?.dutyOrder ?? {};

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

  const getDateOnly = (d: string) => new Date(d).toISOString().split('T')[0];

  if (authLoading || (loading && scheduleLoading)) {
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

  const myDuties = (duties ?? []).filter((d) => d.isCurrentUser);
  const otherDuties = (duties ?? []).filter((d) => !d.isCurrentUser);

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
                2-Week Duty Schedule
              </h2>

              {scheduleLoading ? (
                <div className="loading-container">
                  <div className="loading-spinner"></div>
                  <p className="loading-text">Loading schedule...</p>
                </div>
              ) : schedule.length > 0 ? (
                (() => {
                  const allSchedule = schedule;

                  const week1Days = allSchedule.filter(d => getDateOnly(d.date) < '2026-07-12');
                  const week2Days = allSchedule.filter(d => getDateOnly(d.date) >= '2026-07-12');

                  const allDuties = new Set<string>();
                  allSchedule.forEach(day => {
                    if (day.duties && Array.isArray(day.duties)) {
                      day.duties.forEach(duty => {
                        if (duty?.duty_name) allDuties.add(duty.duty_name);
                      });
                    }
                  });
                  const sortedDuties = Array.from(allDuties).sort(
                    (a, b) => (dutyOrder[a] ?? 99) - (dutyOrder[b] ?? 99)
                  );

                  const buildDutyMap = (days: ScheduleDay[]) => {
                    const map: { [duty: string]: { [date: string]: string } } = {};
                    sortedDuties.forEach(d => { map[d] = {}; });
                    days.forEach(day => {
                      const dateKey = getDateOnly(day.date);
                      if (day.duties && Array.isArray(day.duties)) {
                        day.duties.forEach(duty => {
                          if (duty?.duty_name && duty?.team_name) {
                            map[duty.duty_name][dateKey] = duty.team_name;
                          }
                        });
                      }
                    });
                    return map;
                  };

                  const renderWeekTable = (days: ScheduleDay[], weekLabel: string, isOpen: boolean, onToggle: () => void) => {
                    if (days.length === 0) return null;
                    const dutyMap = buildDutyMap(days);

                    return (
                      <div className="week-table-wrapper">
                        <button className="week-table-toggle" onClick={onToggle} aria-expanded={isOpen}>
                          <span className="week-table-title">{weekLabel}</span>
                          <span className={`week-toggle-chevron ${isOpen ? 'open' : ''}`}>▾</span>
                        </button>
                        {isOpen && (
                          <div className="schedule-table-container">
                            <table className="schedule-table">
                              <thead>
                                <tr>
                                  <th className="duty-name-column">Duty</th>
                                  {days.map(day => {
                                    const dateOnly = getDateOnly(day.date);
                                    const isFreedom = dateOnly === '2026-07-11';
                                    const isPrepWeek = dateOnly === '2026-07-04' || dateOnly === '2026-07-05';
                                    return (
                                      <th key={dateOnly} className="day-column">
                                        <div className="day-header">
                                          <span className="day-weekday">
                                            {new Date(day.date).toLocaleDateString('en-GB', { weekday: 'short' })}
                                          </span>
                                          <span className="day-date-label">
                                            {new Date(day.date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                                          </span>
                                          {isFreedom ? (
                                            <span className="week-badge-small prep-week">FREEDOM</span>
                                          ) : isPrepWeek ? (
                                            <span className="week-badge-small prep-week">Prep</span>
                                          ) : day.week ? (
                                            <span className={`week-badge-small ${day.week === 'Week A' ? 'week-a' : 'week-b'}`}>
                                              {day.week}
                                            </span>
                                          ) : null}
                                        </div>
                                      </th>
                                    );
                                  })}
                                </tr>
                              </thead>
                              <tbody>
                                {sortedDuties.map(dutyName => (
                                  <tr key={dutyName} className="schedule-row">
                                    <td className="duty-name-cell">{dutyName}</td>
                                    {days.map(day => {
                                      const dateOnly = getDateOnly(day.date);
                                      const teamName = dutyMap[dutyName][dateOnly];
                                      return (
                                        <td key={dateOnly} className="duty-cell">
                                          {teamName ? (
                                            <span className="team-number">
                                              {teamName.replace(/team\s*/i, '')}
                                            </span>
                                          ) : (
                                            <span className="no-duty">—</span>
                                          )}
                                        </td>
                                      );
                                    })}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    );
                  };

                  return (
                    <div className="two-week-schedule">
                      {renderWeekTable(week1Days, 'Week 1 — Starting Sat 4 Jul', week1Open, () => setWeek1Open(o => !o))}
                      {renderWeekTable(week2Days, 'Week 2 — Starting Sun 12 Jul', week2Open, () => setWeek2Open(o => !o))}
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

    </>
  );
}
