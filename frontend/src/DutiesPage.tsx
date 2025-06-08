import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "./Navbar";

type Duty = {
  id: string;
  name: string;
  description: string;
  members: { name: string; week: string }[];
  isCurrentUser: boolean;
};

export default function DutiesPage() {
  const [duties, setDuties] = useState<Duty[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const storedUser = localStorage.getItem("currentUser");
    if (!storedUser) {
      navigate("/login");
      return;
    }

    const fetchDuties = async () => {
      try {
        const res = await fetch("/api/duties/today");
        if (!res.ok) throw new Error(`Failed to fetch duties: ${res.statusText}`);
        
        const data: any[] = await res.json();
        console.log("Raw duties from API:", data);
        
        const mapped: Duty[] = data.map((d) => ({
          id: d.id,
          name: d.name,
          description: d.duty_description,
          members: d.members,
          isCurrentUser: d.is_current_user,
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

    fetchDuties();
  }, [navigate]);

  // Get current date for display
  const getCurrentDate = () => {
    return new Date().toLocaleDateString('en-GB', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    });
  };

  if (loading) {
    return (
      <>
        <Navbar />
        <div className="duties-page">
          <div className="loading-container">
            <div className="loading-spinner"></div>
            <p className="loading-text">Loading today's duties...</p>
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
            <h1 className="duties-title">📋 Today's Duties</h1>
            <p className="duties-date">{getCurrentDate()}</p>
          </div>
        </header>

        {error && (
          <div className="error-message">
            <div className="error-icon">⚠️</div>
            <div className="error-text">
              Failed to load duties: {error}
            </div>
          </div>
        )}

        <main className="duties-main">
          {/* Your Duties Section */}
          <section className="duties-section your-duties">
            <h2 className="section-title">
              <span className="section-icon">👤</span>
              Your Duties
            </h2>
            
            {myDuties.length > 0 ? (
              <div className="duties-grid">
                {myDuties.map((duty) => (
                  <div key={duty.id} className="duty-card your-duty-card">
                    <div className="duty-card-header">
                      <h3 className="duty-name">{duty.name}</h3>
                      <div className="duty-badge your-duty-badge">Your Duty</div>
                    </div>
                    <div className="duty-card-body">
                      <p className="duty-description">{duty.description}</p>
                      {duty.members.length > 0 && (
                        <div className="duty-members">
                          <div className="members-label">👥 Team Members:</div>
                          <div className="members-list">
                            {duty.members.map((member, index) => (
                              <div key={index} className="member-item">
                                <span className="member-name">{member.name}</span>
                                <span className="member-week">Week {member.week}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
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
                {otherDuties.map((duty) => (
                  <div key={duty.id} className="duty-card other-duty-card">
                    <div className="duty-card-header">
                      <h3 className="duty-name">{duty.name}</h3>
                      <div className="duty-badge other-duty-badge">Team Duty</div>
                    </div>
                    <div className="duty-card-body">
                      <p className="duty-description">{duty.description}</p>
                      {duty.members.length > 0 && (
                        <div className="duty-members">
                          <div className="members-label">👥 Assigned to:</div>
                          <div className="members-list">
                            {duty.members.map((member, index) => (
                              <div key={index} className="member-item">
                                <span className="member-name">{member.name}</span>
                                <span className="member-week">Week {member.week}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
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