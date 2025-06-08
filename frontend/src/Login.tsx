import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

function Login() {
  const [users, setUsers] = useState<string[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>("");
  const navigate = useNavigate(); // React Router's navigation hook

  useEffect(() => {
    fetch("/get-users")
      .then((response) => response.json())
      .then((data: { users: string[] }) => {
        console.log("Fetched users:", data.users);
        setUsers(data.users || []);
      })
      .catch((error) => console.error("Error fetching users:", error));
  }, []);

  // Handle user selection using relative URL
  const handleLogin = async () => {
    if (!selectedUser) {
      alert("Please select a user!");
      return;
    }

    try {
      const response = await fetch("/select-user", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_name: selectedUser }),
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      // Store user state in localStorage
      localStorage.setItem("is_logged_in", data.is_logged_in ? "true" : "false");
      if (data.user_section) {
        localStorage.setItem("user_section", data.user_section);
      } else {
        localStorage.removeItem("user_section");
      }
      localStorage.setItem("is_leader", data.is_leader ? "true" : "false");

      alert(data.message);

      // Store user in localStorage before redirecting
      localStorage.setItem("currentUser", selectedUser);

      // Redirect to home page
      navigate("/");
    } catch (error) {
      console.error("Error selecting user:", error);
      alert("Failed to select user. Please try again.");
    }
  };

  return (
    <div className="container text-center">
      <h1>Select Your User</h1>
      <div className="input-group mb-3 justify-content-center">
        <select
          className="form-select"
          style={{ width: "50%" }}
          value={selectedUser}
          onChange={(e) => setSelectedUser(e.target.value)}
        >
          <option value="">--Select a user--</option>
          {users.map((user) => (
            <option key={user} value={user}>
              {user}
            </option>
          ))}
        </select>
        <button className="btn btn-primary ms-3" onClick={handleLogin}>
          Confirm
        </button>
      </div>
    </div>
  );
}

export default Login;