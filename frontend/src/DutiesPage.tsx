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
  const navigate = useNavigate();

  useEffect(() => {
    const storedUser = localStorage.getItem("currentUser");
    if (!storedUser) {
      navigate("/login");
      return;
    }

    fetch("/api/duties/today")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch duties");
        return res.json();
      })
      .then((data: any[]) => {
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
      })
      .catch((err) => {
        console.error(err);
      })
      .finally(() => setLoading(false));
  }, [navigate]);

  if (loading) {
    return (
      <div>
        <Navbar />
        <div className="container text-center mt-5">
          <p>Loading duties…</p>
        </div>
      </div>
    );
  }

  const myDuties = duties.filter((d) => d.isCurrentUser);
  const otherDuties = duties.filter((d) => !d.isCurrentUser);

  return (
    <div>
      <Navbar />
      <div className="container mt-5">
        <h1 className="mb-4">Today's Duties</h1>

        {myDuties.length > 0 ? (
          <section className="mb-5">
            <h2>Your Duties</h2>
            {myDuties.map((d) => (
              <div key={d.id} className="mb-3">
                <h3>{d.name}</h3>
                <p>{d.description}</p>
                <p>
                  <strong>With:</strong> {d.members.map(m => `${m.name} (${m.week})`).join(", ")}
                </p>
              </div>
            ))}
          </section>
        ) : (
          <section className="mb-5">
            <div className="alert alert-warning">
              You have no duty assigned today.
            </div>
          </section>
        )}

        <section>
          <h2>Other Duties</h2>
          {otherDuties.length > 0 ? (
            otherDuties.map((d) => (
              <div key={d.id} className="card mb-3">
                <div className="card-body">
                  <h3 className="card-title">{d.name}</h3>
                  <p className="card-text">{d.description}</p>
                  <p className="card-text">
                    <small className="text-muted">
                      Members: {d.members.map(m => `${m.name} (${m.week})`).join(", ")}
                    </small>
                  </p>
                </div>
              </div>
            ))
          ) : (
            <p>No other duties today.</p>
          )}
        </section>
      </div>
    </div>
  );
}