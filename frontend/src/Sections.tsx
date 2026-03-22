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

  const navigate = useNavigate();

  useEffect(() => {
    const initializePage = async () => {
      // Check if user is logged in using the same method as other pages
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

      // Now load the sections data
      await fetchUsersBySection();
    };

    const fetchUsersBySection = async () => {
      try {
        // Add cache busting parameter to force fresh data
        const timestamp = new Date().getTime();
        // Use apiGet which automatically includes username in header/params
        const res = await apiGet(`/api/users/by-section?t=${timestamp}`);
        if (!res.ok) throw new Error(`Failed to fetch users: ${res.statusText}`);
        
        const data: SectionData = await res.json();
        console.log("Users by section data:", data);
        
        // Debug: Log all users and their roles
        data.sections.forEach(section => {
          console.log(`Section: ${section.name}`);
          section.users.forEach(user => {
            console.log(`  User: ${user.name}, Role: ${user.role}, Week: ${user.week}`);
          });
        });
        
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

  const getSectionLeader = (users: User[]): User | null => {
    // Look for both 'Section Leader' and 'Admin' (Admin gets displayed as Section Leader)
    return users.find(user => user.role === 'Section Leader') || null;
  };

  const getOtherUsers = (users: User[]): User[] => {
    return users.filter(user => user.role !== 'Section Leader');
  };

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'Section Leader': return 'bg-purple-100 text-purple-800 border-purple-200'; // This now includes Admin users
      case 'Team Leader': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'Leader': return 'bg-green-100 text-green-800 border-green-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getWeekBadgeColor = (week: string) => {
    switch (week) {
      case 'Week A': return 'bg-green-100 text-green-800 border-green-200';
      case 'Week B': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'Both': return 'bg-indigo-100 text-indigo-800 border-indigo-200'; // Changed to indigo to avoid conflict
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  // Function to determine what to display in the badge
  const getBadgeContent = (user: User) => {
    console.log(`getBadgeContent for ${user.name}: role=${user.role}, week=${user.week}`);
    if (user.role === 'Leader' && user.week) {
      console.log(`Returning week: ${user.week}`);
      return user.week;
    }
    console.log(`Returning role: ${user.role}`);
    return user.role;
  };

  // Function to get the appropriate badge color
  const getBadgeColor = (user: User) => {
    if (user.role === 'Leader' && user.week) {
      return getWeekBadgeColor(user.week);
    }
    return getRoleBadgeColor(user.role);
  };

  // Filter sections based on role filter
  const getFilteredSections = () => {
    if (!sectionsData) return [];
    
    if (filterRole === "all") {
      return sectionsData.sections;
    }
    
    return sectionsData.sections
      .map(section => ({
        ...section,
        users: section.users.filter(user => {
          // Handle the role filtering - Section Leader filter should match both Section Leader and Admin
          if (filterRole === "Section Leader") {
            return user.role === "Section Leader"; // This now includes converted Admin users
          }
          return user.role === filterRole;
        }),
        filtered_count: section.users.filter(user => {
          if (filterRole === "Section Leader") {
            return user.role === "Section Leader";
          }
          return user.role === filterRole;
        }).length
      }))
      .filter(section => section.filtered_count > 0);
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

  const filteredSections = getFilteredSections();

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
            <label htmlFor="role-filter" className="filter-label">
              🔍 Filter by Role
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
        </section>

        <section className="sections-grid-section">
          <div className="sections-grid">
            {filteredSections.length > 0 ? (
              filteredSections.map((section) => {
                const sectionLeader = getSectionLeader(section.users);
                const otherUsers = getOtherUsers(section.users);
                const displayUsers = filterRole === "all" ? section.users : section.users.filter(user => user.role === filterRole);
                
                return (
                  <div key={section.name} className="section-card">
                    <div className="section-card-header">
                      <h3 className="section-title">{section.name}</h3>
                      <div className="user-count-badge">
                        {filterRole === "all" ? section.user_count : displayUsers.length} users
                      </div>
                    </div>
                    
                    <div className="section-card-body">
                      {displayUsers.length > 0 ? (
                        <div className="users-list">
                          {filterRole === "all" ? (
                            <>
                              {/* Section Leader First */}
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
                              
                              {/* Other Users */}
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
                            </>
                          ) : (
                            /* Filtered View */
                            displayUsers.map((user, index) => (
                              <div key={index} className="user-item">
                                <div className="user-info">
                                  <span className="user-name">{user.name}</span>
                                  <span className={`role-badge ${getBadgeColor(user)}`}>
                                    {getBadgeContent(user)}
                                  </span>
                                </div>
                              </div>
                            ))
                          )}
                        </div>
                      ) : (
                        <div className="no-users">
                          <div className="no-users-icon">👤</div>
                          <p className="no-users-text">
                            {filterRole === "all" 
                              ? "No users in this section"
                              : `No ${filterRole.toLowerCase()}s in this section`
                            }
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="no-sections-message">
                <div className="no-sections-icon">🔍</div>
                <h3 className="no-sections-title">No Results Found</h3>
                <p className="no-sections-text">
                  {filterRole === "all" 
                    ? "No sections available"
                    : `No sections have users with the role "${filterRole}"`
                  }
                </p>
              </div>
            )}
          </div>
        </section>

        <footer className="sections-page-footer">
          <p className="footer-text">
            💡 Section leaders are highlighted and appear first in each section.
          </p>
        </footer>
      </div>
    </>
  );
}