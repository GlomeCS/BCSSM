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
    <div>
      <Navbar /> {/* Reusable navigation bar */}
      <div className="container text-center mt-5">
        <h1 className="mb-4">Welcome to Ballyholme CSSM 2025!!! 🎉</h1>
        {currentUser ? (
          <>
            <p id="currentUser">
              Current User: <strong>{currentUser}</strong>
            </p>
            <h2 className="mt-4">Your Duty</h2>
            <div id="content">
              {loading ? (
                <p>Loading duty info...</p>
              ) : dutyMessage ? (
                <div className="alert alert-success text-center">
                  {dutyMessage}
                </div>
              ) : (
                <div className="alert alert-warning text-center">
                  No duty assigned today. Please check the duty assignments.
                </div>
              )}
            </div>
          </>
        ) : (
          <p>Redirecting to login...</p>
        )}
      </div>
    </div>
  );
}

export default Home;