import { useNavigate } from "react-router-dom";

function Navbar() {
    const navigate = useNavigate();
    const currentUser = localStorage.getItem("currentUser");

    const handleLogout = () => {
        localStorage.removeItem("currentUser");
        navigate("/login");
    };

    if (!currentUser) return null; // Don't render if user is not logged in

    return (
        <nav className="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
            <div className="container-fluid">
                <a className="navbar-brand" href="/">Ballyholme CSSM Helper</a>
                <button className="navbar-toggler" type="button" data-bs-toggle="collapse" 
                        data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" 
                        aria-label="Toggle navigation">
                    <span className="navbar-toggler-icon"></span>
                </button>  
                <div className="collapse navbar-collapse" id="navbarNav">
                    <ul className="navbar-nav ms-auto">
                        <li className="nav-item"><a className="nav-link" href="/">Home</a></li>
                        <li className="nav-item"><a className="nav-link" href="/duty-teams">Duty Teams</a></li>
                        <li className="nav-item"><a className="nav-link" href="/react/devos-feedback">Devos Feedback</a></li>
                        <li className="nav-item">
                            <button className="btn btn-danger nav-link text-white border-0" 
                                    onClick={handleLogout}>
                                Logout
                            </button>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
    );
}

export default Navbar;