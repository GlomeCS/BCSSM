import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "./Navbar"; // Import the reusable Navbar component

function Home() {
  const [currentUser, setCurrentUser] = useState<string | null>(null);
  const [dutyMessage, setDutyMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const navigate = useNavigate();
  console.log("Home component rendered");

  // On component mount, retrieve the current user and fetch duty info.
  useEffect(() => {
    console.log("Home useEffect triggered");
    const storedUser = localStorage.getItem("currentUser");
    console.log("Stored user:", storedUser);
    if (!storedUser) {
      navigate("/login");
      console.log("No user found, redirecting to login.");
    } else {
      setCurrentUser(storedUser);
      console.log("Current user:", storedUser);
      // Fetch duty info for the user from the API endpoint.
      fetch("/duty-teams")
        .then((response) => response.json())
        .then((data) => {
          // Expect the API to return JSON like: { user: <username>, duty_message: <string> }
          if (data && data.user) {
            setDutyMessage(data.duty_message);
          }
          setLoading(false);
        })
        .catch((error) => {
          console.error("Error fetching duty info:", error);
          setLoading(false);
        });
        console.log("Fetching duty info...");
    }
  }, [navigate]);

  return (
    <div className="home-page">
      <Navbar />
      <header className="hero">
        <div className="hero-content">
          <h1>Welcome to Ballyholme CSSM 2025</h1>
        </div>
      </header>
      <section className="info-section">
        {currentUser && (
          <p className="user-info">
            Good mae <strong>{currentUser}</strong>
          </p>
        )}
        <div className="duty-card">
          {loading ? (
            <p>Loading your duty info...</p>
          ) : dutyMessage ? (
            <p>Your duty today is {dutyMessage}</p>
          ) : (
            <p>No duty assigned today.</p>
          )}
        </div>
      </section>
    </div>
  );
}

export default Home;