import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "./Navbar";

type User = {
  name: string;
  role: string;
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
    const storedUser = localStorage.getItem("currentUser");
    if (!storedUser) {
      navigate("/login");
      return;
    }

    const fetchUsersBySection = async () => {
      try {
        const res = await fetch("/api/users/by-section");
        if (!res.ok) throw new Error(`Failed to fetch users: ${res.statusText}`);
        
        const data: SectionData = await res.json();
        console.log("Users by section data:", data);
        
        // Debug: Log all users and their roles
        data.sections.forEach(section => {
          console.log(`Section: ${section.name}`);
          section.users.forEach(user => {
            console.log(`  User: ${user.name}, Role: ${user.role}`);
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

    fetchUsersBySection();
  }, []);

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
                                    <span className={`role-badge ${getRoleBadgeColor(sectionLeader.role)}`}>
                                      {sectionLeader.role}
                                    </span>
                                  </div>
                                </div>
                              )}
                              
                              {/* Other Users */}
                              {otherUsers.map((user, index) => (
                                <div key={index} className="user-item">
                                  <div className="user-info">
                                    <span className="user-name">{user.name}</span>
                                    <span className={`role-badge ${getRoleBadgeColor(user.role)}`}>
                                      {user.role}
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
                                  <span className={`role-badge ${getRoleBadgeColor(user.role)}`}>
                                    {user.role}
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

        <footer className="page-footer">
          <p className="footer-text">
            💡 Section leaders are highlighted and appear first in each section.
          </p>
        </footer>
      </div>

      <style>{`
        .users-page {
          min-height: 100vh;
          padding: var(--space-16, 4rem) var(--space-4, 1rem) var(--space-8, 2rem);
          max-width: 1200px;
          margin: 0 auto;
          width: 100%;
          display: flex;
          flex-direction: column;
          gap: var(--space-8, 2rem);
        }

        .page-header {
          background: var(--bg-glass, rgba(255, 255, 255, 0.95));
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: var(--radius-2xl, 1.5rem);
          padding: var(--space-8, 2rem);
          text-align: center;
          box-shadow: var(--shadow-lg, 0 10px 15px -3px rgba(0, 0, 0, 0.1));
          position: relative;
          overflow: hidden;
        }

        .page-header::before {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          height: 3px;
          background: linear-gradient(90deg, var(--color-primary, #2563eb), var(--color-accent, #eab308), var(--color-primary, #2563eb));
          animation: shimmer 3s ease-in-out infinite;
        }

        @keyframes shimmer {
          0%, 100% { opacity: 0.6; }
          50% { opacity: 1; }
        }

        .page-header-content {
          position: relative;
          z-index: 1;
        }

        .page-title {
          font-size: clamp(var(--font-size-2xl, 1.5rem), 4vw, var(--font-size-4xl, 2.25rem));
          font-weight: 700;
          background: linear-gradient(135deg, var(--color-primary-dark, #1d4ed8), var(--color-accent, #eab308));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          margin-bottom: var(--space-2, 0.5rem);
          line-height: 1.2;
        }

        .page-subtitle {
          color: var(--color-text-secondary, #64748b);
          font-size: var(--font-size-lg, 1.125rem);
          font-weight: 400;
          margin: 0;
          opacity: 0.8;
        }

        .filter-section {
          display: flex;
          justify-content: center;
          align-items: center;
        }

        .filter-container {
          background: var(--bg-card, rgba(255, 255, 255, 0.98));
          backdrop-filter: blur(20px);
          border: 1px solid rgba(37, 99, 235, 0.1);
          border-radius: var(--radius-xl, 1rem);
          padding: var(--space-6, 1.5rem);
          box-shadow: var(--shadow-md, 0 4px 6px -1px rgba(0, 0, 0, 0.1));
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-3, 0.75rem);
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          max-width: 400px;
        }

        .filter-container:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow-lg, 0 10px 15px -3px rgba(0, 0, 0, 0.1));
        }

        .filter-label {
          font-size: var(--font-size-lg, 1.125rem);
          font-weight: 600;
          color: var(--color-text-primary, #1e293b);
          margin: 0;
        }

        .role-filter {
          width: 100%;
          padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
          border: 2px solid var(--color-primary-light, #93c5fd);
          border-radius: var(--radius-lg, 0.75rem);
          font-size: var(--font-size-base, 1rem);
          font-weight: 500;
          color: var(--color-text-primary, #1e293b);
          background: white;
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          min-width: 200px;
          text-align: center;
        }

        .role-filter:focus {
          outline: none;
          border-color: var(--color-primary, #2563eb);
          box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
          transform: scale(1.02);
        }

        .sections-grid-section {
          flex: 1;
        }

        .sections-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
          gap: var(--space-6, 1.5rem);
          width: 100%;
          align-items: start;
        }

        /* Center the last item if it's alone in its row */
        .sections-grid > .section-card:last-child:nth-child(odd) {
          grid-column: 1 / -1;
          justify-self: center;
          max-width: 500px;
        }

        .section-card {
          background: var(--bg-card, rgba(255, 255, 255, 0.98));
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: var(--radius-xl, 1rem);
          box-shadow: var(--shadow-md, 0 4px 6px -1px rgba(0, 0, 0, 0.1));
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          overflow: hidden;
          display: flex;
          flex-direction: column;
          height: fit-content;
          width: 100%;
        }

        .section-card:hover {
          transform: translateY(-4px);
          box-shadow: var(--shadow-xl, 0 20px 25px -5px rgba(0, 0, 0, 0.1));
        }

        .section-card-header {
          padding: var(--space-4, 1rem) var(--space-6, 1.5rem);
          background: linear-gradient(135deg, rgba(37, 99, 235, 0.05), rgba(234, 179, 8, 0.05));
          border-bottom: 1px solid rgba(37, 99, 235, 0.1);
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: var(--space-3, 0.75rem);
        }

        .section-title {
          font-size: var(--font-size-lg, 1.125rem);
          font-weight: 600;
          color: var(--color-text-primary, #1e293b);
          margin: 0;
          flex: 1;
        }

        .user-count-badge {
          background: var(--color-secondary, #fef3c7);
          color: var(--color-text-primary, #1e293b);
          padding: var(--space-1, 0.25rem) var(--space-3, 0.75rem);
          border-radius: var(--radius-lg, 0.75rem);
          font-size: var(--font-size-sm, 0.875rem);
          font-weight: 500;
          border: 1px solid rgba(234, 179, 8, 0.2);
        }

        .section-card-body {
          padding: var(--space-6, 1.5rem);
          flex: 1;
          display: flex;
          flex-direction: column;
        }

        .users-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-3, 0.75rem);
        }

        .user-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
          background: rgba(148, 163, 184, 0.05);
          border-radius: var(--radius-md, 0.5rem);
          transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
          border-left: 3px solid var(--color-primary-light, #93c5fd);
        }

        .user-item:hover {
          background: rgba(37, 99, 235, 0.05);
          transform: translateX(4px);
        }

        .leader-item {
          background: linear-gradient(135deg, rgba(147, 51, 234, 0.1), rgba(196, 181, 253, 0.1));
          border-left-color: var(--color-accent, #eab308);
          border: 1px solid rgba(147, 51, 234, 0.2);
        }

        .leader-item:hover {
          background: linear-gradient(135deg, rgba(147, 51, 234, 0.15), rgba(196, 181, 253, 0.15));
        }

        .user-info {
          display: flex;
          align-items: center;
          gap: var(--space-3, 0.75rem);
          width: 100%;
        }

        .user-name {
          font-weight: 500;
          color: var(--color-text-primary, #1e293b);
          flex: 1;
          font-size: var(--font-size-base, 1rem);
        }

        .leader-name {
          font-weight: 700;
          color: var(--color-primary-dark, #1d4ed8);
          font-size: var(--font-size-lg, 1.125rem);
        }

        .role-badge {
          padding: var(--space-1, 0.25rem) var(--space-2, 0.5rem);
          border-radius: var(--radius-md, 0.5rem);
          font-size: var(--font-size-xs, 0.75rem);
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          white-space: nowrap;
        }

        .role-badge.bg-purple-100 {
          background: linear-gradient(135deg, var(--color-accent, #eab308), #fbbf24);
          color: white;
          box-shadow: 0 2px 4px rgba(234, 179, 8, 0.2);
        }

        .role-badge.bg-blue-100 {
          background: linear-gradient(135deg, var(--color-primary, #2563eb), var(--color-primary-dark, #1d4ed8));
          color: white;
          box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
        }

        .role-badge.bg-green-100 {
          background: linear-gradient(135deg, var(--color-success, #10b981), #059669);
          color: white;
          box-shadow: 0 2px 4px rgba(16, 185, 129, 0.2);
        }

        .role-badge.bg-gray-100 {
          background: linear-gradient(135deg, var(--color-text-secondary, #64748b), var(--color-text-muted, #94a3b8));
          color: white;
          box-shadow: 0 2px 4px rgba(100, 116, 139, 0.2);
        }

        .no-users {
          text-align: center;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-3, 0.75rem);
          opacity: 0.6;
          padding: var(--space-6, 1.5rem);
        }

        .no-users-icon {
          font-size: 2.5rem;
          opacity: 0.5;
        }

        .no-users-text {
          color: var(--color-text-muted, #94a3b8);
          font-style: italic;
          margin: 0;
          font-size: var(--font-size-base, 1rem);
        }

        .no-sections-message {
          grid-column: 1 / -1;
          background: var(--bg-card, rgba(255, 255, 255, 0.98));
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: var(--radius-xl, 1rem);
          padding: var(--space-12, 3rem) var(--space-8, 2rem);
          text-align: center;
          box-shadow: var(--shadow-md, 0 4px 6px -1px rgba(0, 0, 0, 0.1));
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-4, 1rem);
          opacity: 0.8;
        }

        .no-sections-icon {
          font-size: 3rem;
          opacity: 0.6;
        }

        .no-sections-title {
          font-size: var(--font-size-xl, 1.25rem);
          font-weight: 600;
          color: var(--color-text-primary, #1e293b);
          margin: 0;
        }

        .no-sections-text {
          color: var(--color-text-secondary, #64748b);
          font-size: var(--font-size-base, 1rem);
          line-height: 1.6;
          margin: 0;
        }

        .page-footer {
          background: var(--bg-glass, rgba(255, 255, 255, 0.95));
          backdrop-filter: blur(20px);
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: var(--radius-xl, 1rem);
          padding: var(--space-6, 1.5rem);
          box-shadow: var(--shadow-md, 0 4px 6px -1px rgba(0, 0, 0, 0.1));
          text-align: center;
        }

        .footer-text {
          color: var(--color-text-secondary, #64748b);
          font-size: var(--font-size-sm, 0.875rem);
          line-height: 1.5;
          margin: 0;
          font-style: italic;
        }

        .loading-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          min-height: 60vh;
          gap: var(--space-4, 1rem);
        }

        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--color-primary-light, #93c5fd);
          border-top: 3px solid var(--color-primary, #2563eb);
          border-radius: 50%;
          animation: spin 1s linear infinite;
        }

        .loading-text {
          color: var(--color-text-secondary, #64748b);
          font-size: var(--font-size-lg, 1.125rem);
          font-weight: 500;
        }

        .error-message {
          background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(248, 113, 113, 0.1));
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: var(--radius-lg, 0.75rem);
          padding: var(--space-4, 1rem);
          display: flex;
          align-items: center;
          gap: var(--space-3, 0.75rem);
          animation: errorSlideIn 0.3s ease-out;
        }

        @keyframes errorSlideIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .error-icon {
          font-size: var(--font-size-xl, 1.25rem);
          flex-shrink: 0;
        }

        .error-text {
          color: #dc2626;
          font-weight: 500;
          font-size: var(--font-size-sm, 0.875rem);
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        /* Responsive Design */
        @media (max-width: 768px) {
          .users-page {
            padding: var(--space-16, 4rem) var(--space-3, 0.75rem) var(--space-6, 1.5rem);
            gap: var(--space-6, 1.5rem);
          }

          .page-header {
            padding: var(--space-6, 1.5rem);
            border-radius: var(--radius-xl, 1rem);
          }

          .sections-grid {
            grid-template-columns: 1fr;
            gap: var(--space-4, 1rem);
          }

          .section-card-header {
            padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
            flex-direction: column;
            align-items: flex-start;
            gap: var(--space-2, 0.5rem);
          }

          .user-count-badge {
            align-self: flex-end;
          }

          .filter-container {
            padding: var(--space-4, 1rem);
            width: 100%;
            max-width: 300px;
          }

          .role-filter {
            min-width: unset;
            width: 100%;
          }

          .no-sections-message {
            padding: var(--space-8, 2rem) var(--space-4, 1rem);
          }
        }

        @media (max-width: 480px) {
          .users-page {
            padding: var(--space-16, 4rem) var(--space-2, 0.5rem) var(--space-4, 1rem);
          }

          .page-header {
            padding: var(--space-4, 1rem);
          }

          .section-card-body {
            padding: var(--space-4, 1rem);
          }

          .sections-grid {
            gap: var(--space-3, 0.75rem);
          }

          .page-title {
            font-size: var(--font-size-2xl, 1.5rem);
          }

          .user-item {
            flex-direction: column;
            align-items: flex-start;
            gap: var(--space-2, 0.5rem);
          }

          .role-badge {
            align-self: flex-end;
          }
        }

        /* Accessibility improvements */
        @media (prefers-reduced-motion: reduce) {
          .section-card,
          .filter-container,
          .user-item,
          .loading-spinner {
            transition-duration: 0.01ms !important;
            animation: none !important;
          }
        }

        /* High contrast mode support */
        @media (prefers-contrast: high) {
          .section-card,
          .page-header,
          .filter-container,
          .page-footer,
          .no-sections-message {
            background: white;
            border: 2px solid black;
          }

          .page-title,
          .section-title,
          .user-name,
          .filter-label {
            color: black;
          }

          .role-badge {
            background: black !important;
            color: white !important;
          }
        }

        /* Focus states for keyboard navigation */
        .role-filter:focus,
        .section-card:focus-within {
          outline: 2px solid var(--color-primary, #2563eb);
          outline-offset: 2px;
        }
      `}</style>
    </>
  );
}