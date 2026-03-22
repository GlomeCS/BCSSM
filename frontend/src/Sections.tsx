import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "./Navbar";
import { apiGet, getCurrentUser, isLoggedIn, validateAuth } from '../api';
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
  const [sectionsData, setSectionsData] = useState<SectionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterRole, setFilterRole] = useState<string>("all");
  const [filterWeek, setFilterWeek] = useState<string>("all");
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());

  const navigate = useNavigate();

  useEffect(() => {
    const initializePage = async () => {
      if (!isLoggedIn()) {
        navigate("/login");
        return;
      }

      const user = getCurrentUser();
      if (!user) {
        navigate("/login");
        return;
      }

      const isValid = await validateAuth();
      if (!isValid) {
        localStorage.clear();
        navigate("/login");
        return;
      }

      await fetchUsersBySection();
    };

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
        setLoading(false);
      }
    };

    initializePage();
  }, [navigate]);

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

  const userMatchesWeek = (user: User, week: string): boolean => {
    if (week === "all") return true;
    if (!user.week) return true; // no week assigned (e.g. Section/Team Leaders), always show
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
          users = users.filter(user => userMatchesWeek(user, filterWeek));
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

  if (loading) {
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
            <h1 className="page-title">👥 Users by Section</h1>
            <p className="page-subtitle">
              {sectionsData ? `${sectionsData.total_users} users across ${sectionsData.total_sections} sections` : ''}
            </p>
          </div>
        </header>

        {error && (
          <div className="error-message">
            <div className="error-icon">⚠️</div>
            <div className="error-text">
              Failed to load users: {error}
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

                return (
                  <div key={section.name} className={`section-card ${isCollapsed ? 'section-card--collapsed' : ''}`}>
                    <button
                      className="section-card-header section-card-header--clickable"
                      onClick={() => toggleSection(section.name)}
                      aria-expanded={!isCollapsed}
                    >
                      <h3 className="section-title">{section.name}</h3>
                      <div className="section-header-right">
                        <div className="user-count-badge">
                          {isFiltering ? section.users.length : section.user_count} user{(isFiltering ? section.users.length : section.user_count) !== 1 ? 's' : ''}
                        </div>
                        <span className={`collapse-chevron ${isCollapsed ? 'collapse-chevron--collapsed' : ''}`}>
                          ▼
                        </span>
                      </div>
                    </button>

                    {!isCollapsed && (
                      <div className="section-card-body">
                        {section.users.length > 0 ? (
                          <div className="users-list">
                            {sectionLeader && (
                              <div className="user-item leader-item">
                                <div className="user-info">
                                  <span className="user-name leader-name">{sectionLeader.name}</span>
                                  <span className={`role-badge ${getBadgeColor(sectionLeader)}`}>
                                    {getBadgeContent(sectionLeader)}
                                  </span>
                                </div>
                              </div>
                            )}

                            {otherUsers.map((user, index) => (
                              <div key={index} className="user-item">
                                <div className="user-info">
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
                            <p className="no-users-text">No matching users in this section</p>
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
