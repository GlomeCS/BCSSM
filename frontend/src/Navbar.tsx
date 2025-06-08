import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

function Navbar() {
    const navigate = useNavigate();
    const currentUser = localStorage.getItem("currentUser");
    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isScrolled, setIsScrolled] = useState(false);

    const handleLogout = () => {
        localStorage.removeItem("currentUser");
        navigate("/login");
    };

    const toggleMenu = () => {
        setIsMenuOpen(!isMenuOpen);
    };

    const closeMenu = () => {
        setIsMenuOpen(false);
    };

    // Handle scroll effect for navbar background
    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 20);
        };
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: Event) => {
            if (isMenuOpen && !(event.target as Element).closest('.navbar')) {
                closeMenu();
            }
        };
        document.addEventListener('click', handleClickOutside);
        return () => document.removeEventListener('click', handleClickOutside);
    }, [isMenuOpen]);

    // Prevent body scroll when mobile menu is open
    useEffect(() => {
        if (isMenuOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = 'unset';
        }
        return () => {
            document.body.style.overflow = 'unset';
        };
    }, [isMenuOpen]);

    if (!currentUser) return null;

    return (
        <nav className={`navbar ${isScrolled ? 'scrolled' : ''}`}>
            <div className="navbar-container">
                <a href="/" className="navbar-brand">
                    Ballyholme CSSM Helper
                </a>

                {/* Desktop Menu */}
                <ul className="navbar-menu">
                    <li><a href="/" className="nav-link">Home</a></li>
                    <li><a href="/duties" className="nav-link">Duties</a></li>
                    <li><a href="/react/devos-feedback" className="nav-link">Devos Feedback</a></li>
                    <li>
                        <button onClick={handleLogout} className="logout-btn">
                            Logout
                        </button>
                    </li>
                </ul>

                {/* Mobile Menu Button */}
                <button 
                    className={`mobile-menu-button ${isMenuOpen ? 'active' : ''}`}
                    onClick={toggleMenu}
                    aria-label="Toggle navigation menu"
                    aria-expanded={isMenuOpen}
                >
                    <span className="hamburger-line"></span>
                    <span className="hamburger-line"></span>
                    <span className="hamburger-line"></span>
                </button>
            </div>

            {/* Mobile Menu Overlay */}
            <div className={`mobile-menu-overlay ${isMenuOpen ? 'active' : ''}`}>
                <div className={`mobile-menu ${isMenuOpen ? 'active' : ''}`}>
                    <ul className="mobile-menu-list">
                        <li>
                            <a href="/" className="mobile-nav-link" onClick={closeMenu}>
                                🏠 Home
                            </a>
                        </li>
                        <li>
                            <a href="/duties" className="mobile-nav-link" onClick={closeMenu}>
                                📋 Duties
                            </a>
                        </li>
                        <li>
                            <a href="/react/devos-feedback" className="mobile-nav-link" onClick={closeMenu}>
                                💬 Devos Feedback
                            </a>
                        </li>
                        <li>
                            <button onClick={handleLogout} className="mobile-logout-btn">
                                🚪 Logout
                            </button>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
    );
}

export default Navbar;