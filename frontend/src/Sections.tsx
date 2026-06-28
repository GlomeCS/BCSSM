import { useState, useEffect } from "react";
import Navbar from "./Navbar";
import { apiGet } from '../api';
import { useRequireAuth } from "./hooks/useRequireAuth";
import "./Sections.css";

type User = {
  name: string;
  role: string;
  week?: string;
};

type Section = {
  name: string;
  display_order: number;
  users: User[];
  user_count: number;
};

type SectionData = {
  sections: Section[];
  total_users: number;
  total_sections: number;
};

export default function UsersBySectionPage() {
  const { currentUser, loading: authLoading } = useRequireAuth();
  const [sectionsData, setSectionsData] = useState<SectionData | null>(null);
  const [dataLoading, setDataLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterRole, setFilterRole] = useState<string>("all");
  const [filterWeek, setFilterWeek] = useState<string>("all");
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!currentUser) return;
    const fetchUsersBySection = async () => {
      try {
        const timestamp = new Date().getTime();
        const res = await apiGet(`/api/users/by-section?t=${timestamp}`);
        if (!res.ok) throw new Error(`Failed to fetch users: ${res.statusText}`);

        const data: SectionData = await res.json();
        setSectionsData(data);

      } catch (err) {
        console.error("Error fetching users by section:", err);
        setError((err as Error).message);
      } finally {
        setDataLoading(false);
      }
    };
    fetchUsersBySection();
  }, [currentUser]);

  const toggleSection = (sectionName: string) => {
    setCollapsedSections(prev => {
      const next = new Set(prev);
      if (next.has(sectionName)) {
        next.delete(sectionName);
      } else {
        next.add(sectionName);
      }
      return next;
    });
  };

  const getSectionLeader = (users: User[]): User | null => {
    return users.find(user => user.role === 'Section Leader') || null;
  };

  const getOtherUsers = (users: User[]): User[] => {
    return users.filter(user => user.role !== 'Section Leader');
  };

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'Section Leader': return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'Team Leader': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'Leader': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getWeekBadgeColor = (week: string) => {
    switch (week) {
      case 'Week A': return 'bg-green-100 text-green-800 border-green-200';
      case 'Week B': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'Both': return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getBadgeContent = (user: User) => {
    if (user.role === 'Leader' && user.week) {
      return user.week;
    }
    return user.role;
  };

  const getBadgeColor = (user: User) => {
    if (user.role === 'Leader' && user.week) {
      return getWeekBadgeColor(user.week);
    }
    return getRoleBadgeColor(user.role);
  };

  const SECTION_COLORS: Record<string, { cls: string; color: string }> = {
    minis:  { cls: 'section-color-minis',  color: '#facc15' },
    micros: { cls: 'section-color-micros', color: '#f97316' },
    minors: { cls: 'section-color-minors', color: '#3b82f6' },
    majors: { cls: 'section-color-majors', color: '#ef4444' },
    midis:  { cls: 'section-color-midis',  color: '#10b981' },
    maxis:  { cls: 'section-color-maxis',  color: '#a855f7' },
  };

  const getSectionTheme = (name: string) => {
    const lower = name.toLowerCase();
    const key = Object.keys(SECTION_COLORS).find(k => lower.includes(k));
    return key ? SECTION_COLORS[key] : { cls: '', color: '#6b7280' };
  };

  const userMatchesWeek = (user: User, week: string): boolean => {
    if (week === "all") return true;
    return user.week === week || user.week === 'Both';
  };

  const getFilteredSections = () => {
    if (!sectionsData) return [];

    const isFiltering = filterRole !== "all" || filterWeek !== "all";

    return sectionsData.sections
      .map(section => {
        let users = section.users;

        if (filterRole !== "all") {
          users = users.filter(user => {
            if (filterRole === "Section Leader") return user.role === "Section Leader";
            return user.role === filterRole;
          });
        }

        if (filterWeek !== "all") {
          const matched = users.filter(user => user.week && userMatchesWeek(user, filterWeek));
          if (matched.length > 0) {
            const unassigned = users.filter(user => !user.week);
            users = [...matched, ...unassigned];
          } else {
            users = [];
          }
        }

        return { ...section, users, filtered_count: users.length };
      })
      .filter(section => !isFiltering || section.filtered_count > 0);
  };

  const filteredSections = getFilteredSections();
  const isFiltering = filterRole !== "all" || filterWeek !== "all";

  const allSectionNames = filteredSections.map(s => s.name);
  const allCollapsed = allSectionNames.length > 0 && allSectionNames.every(name => collapsedSections.has(name));

  const toggleAll = () => {
    if (allCollapsed) {
      setCollapsedSections(prev => {
        const next = new Set(prev);
        allSectionNames.forEach(name => next.delete(name));
        return next;
      });
    } else {
      setCollapsedSections(prev => new Set([...prev, ...allSectionNames]));
    }
  };

  if (authLoading || dataLoading) {
    return (
      <>
        <Navbar />
        <div className="users-page">
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p className="loading-text">Loading sections...</p>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <div className="users-page">
        <header className="page-header">
          <div className="page-header-content">
            <h1 className="page-title">👥 Leaders by Section</h1>
            <p className="page-subtitle">
              {sectionsData ? `${sectionsData.total_users} leaders across ${sectionsData.total_sections} sections` : ''}
            </p>
          </div>
        </header>

        {error && (
          <div className="error-message">
            <div className="error-icon">⚠️</div>
            <div className="error-text">
              Failed to load leaders: {error}
            </div>
          </div>
        )}

        <section className="filter-section">
          <div className="filter-container">
            <div className="filter-row">
              <div className="filter-group">
                <label htmlFor="role-filter" className="filter-label">
                  Filter by Role
                </label>
                <select
                  id="role-filter"
                  value={filterRole}
                  onChange={(e) => setFilterRole(e.target.value)}
                  className="role-filter"
                >
                  <option value="all">All Roles</option>
                  <option value="Section Leader">Section Leaders Only</option>
                  <option value="Team Leader">Team Leaders Only</option>
                  <option value="Leader">Leaders Only</option>
                </select>
              </div>

              <div className="filter-group">
                <label htmlFor="week-filter" className="filter-label">
                  Filter by Week
                </label>
                <select
                  id="week-filter"
                  value={filterWeek}
                  onChange={(e) => setFilterWeek(e.target.value)}
                  className="role-filter"
                >
                  <option value="all">All Weeks</option>
                  <option value="Week A">Week A</option>
                  <option value="Week B">Week B</option>
                </select>
              </div>
            </div>

            {filteredSections.length > 0 && (
              <button className="toggle-all-btn" onClick={toggleAll}>
                {allCollapsed ? '▶ Expand All' : '▼ Collapse All'}
              </button>
            )}
          </div>
        </section>

        <section className="sections-grid-section">
          <div className="sections-grid">
            {filteredSections.length > 0 ? (
              filteredSections.map((section) => {
                const isCollapsed = collapsedSections.has(section.name);
                const sectionLeader = getSectionLeader(section.users);
                const otherUsers = getOtherUsers(section.users);

                const triggerId = `section-trigger-${section.name.replace(/\s+/g, '-')}`;
                const panelId = `section-panel-${section.name.replace(/\s+/g, '-')}`;
                const userCount = isFiltering ? section.users.length : section.user_count;

                return (
                  <div key={section.name} className={`section-card ${isCollapsed ? 'section-card--collapsed' : ''} ${getSectionTheme(section.name).cls}`}>
                    <h3 className="section-title">
                      <button
                        id={triggerId}
                        className="section-card-header section-card-header--clickable"
                        onClick={() => toggleSection(section.name)}
                        aria-expanded={!isCollapsed}
                        aria-controls={panelId}
                      >
                        <span className="section-title-text">{section.name}</span>
                        <span className="section-header-right">
                          <span className="user-count-badge">
                            {userCount} leader{userCount !== 1 ? 's' : ''}
                          </span>
                          <span className={`collapse-chevron ${isCollapsed ? 'collapse-chevron--collapsed' : ''}`}>
                            ▼
                          </span>
                        </span>
                      </button>
                    </h3>

                    {!isCollapsed && (
                      <div
                        id={panelId}
                        role="region"
                        aria-labelledby={triggerId}
                        className="section-card-body"
                      >
                        {section.users.length > 0 ? (
                          <div className="users-list">
                            {sectionLeader && (
                              <div className="user-item leader-item" style={{ background: `linear-gradient(135deg, ${getSectionTheme(section.name).color}1a, ${getSectionTheme(section.name).color}0d)`, borderColor: `${getSectionTheme(section.name).color}33` }}>
                                <div className="user-info" style={{ borderLeft: `4px solid ${getSectionTheme(section.name).color}` }}>
                                  <span className="user-name leader-name">{sectionLeader.name}</span>
                                  <span
                                    className={`role-badge ${getBadgeColor(sectionLeader)}`}
                                    style={{ background: getSectionTheme(section.name).color, boxShadow: `0 2px 4px ${getSectionTheme(section.name).color}40` }}
                                  >
                                    {getBadgeContent(sectionLeader)}
                                  </span>
                                </div>
                              </div>
                            )}

                            {otherUsers.map((user, index) => (
                              <div key={index} className="user-item">
                                <div className="user-info" style={{ borderLeft: `4px solid ${getSectionTheme(section.name).color}` }}>
                                  <span className="user-name">{user.name}</span>
                                  <span className={`role-badge ${getBadgeColor(user)}`}>
                                    {getBadgeContent(user)}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="no-users">
                            <div className="no-users-icon">👤</div>
                            <p className="no-users-text">No matching leaders in this section</p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="no-sections-message">
                <div className="no-sections-icon">🔍</div>
                <h3 className="no-sections-title">No Results Found</h3>
                <p className="no-sections-text">
                  {!isFiltering
                    ? "No sections available"
                    : "No sections match the selected filters"
                  }
                </p>
              </div>
            )}
          </div>
        </section>

        <footer className="sections-page-footer">
          <p className="footer-text">
            💡 Section leaders are highlighted and appear first. Click a section header to collapse it.
          </p>
        </footer>
      </div>
    </>
  );
}
