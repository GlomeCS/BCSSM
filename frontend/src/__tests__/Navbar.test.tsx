import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Navbar from '../Navbar';
import { ThemeProvider } from '../ThemeContext';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

const mockNavAuth = vi.hoisted(() => ({
  currentUser: null as string | null,
  logout: vi.fn(),
  loading: false,
  userRole: null as string | null,
  userSection: null as string | null,
  canEditAll: false,
  setUser: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock('../AuthContext', () => ({
  useAuth: () => mockNavAuth,
}));

function renderNavbar() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <Navbar />
      </MemoryRouter>
    </ThemeProvider>
  );
}

describe('Navbar', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    mockNavigate.mockClear();
    mockNavAuth.logout.mockClear();
    mockNavAuth.currentUser = null;
  });

  it('renders nothing when no currentUser in localStorage', () => {
    mockNavAuth.currentUser = null;
    const { container } = renderNavbar();
    expect(container.firstChild).toBeNull();
  });

  it('renders nav links when user is logged in', () => {
    mockNavAuth.currentUser = 'Alice';
    renderNavbar();
    expect(screen.getByText('Ballyholme CSSM Helper')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Duties' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Devos Feedback' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sections' })).toBeInTheDocument();
  });

  it('clicking logout calls logout() and navigates to /login', async () => {
    mockNavAuth.currentUser = 'Alice';
    renderNavbar();
    fireEvent.click(screen.getAllByRole('button', { name: /logout/i })[0]);
    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/login'));
    expect(mockNavAuth.logout).toHaveBeenCalledTimes(1);
  });

  it('mobile menu button toggles aria-expanded', () => {
    mockNavAuth.currentUser = 'Alice';
    renderNavbar();
    const menuBtn = screen.getByRole('button', { name: /toggle navigation menu/i });
    expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(menuBtn);
    expect(menuBtn).toHaveAttribute('aria-expanded', 'true');
  });

  it('mobile menu closes after clicking a link', () => {
    mockNavAuth.currentUser = 'Alice';
    renderNavbar();
    const menuBtn = screen.getByRole('button', { name: /toggle navigation menu/i });
    fireEvent.click(menuBtn);
    expect(menuBtn).toHaveAttribute('aria-expanded', 'true');
    // Click a mobile nav link (there are two "Home" links: desktop + mobile)
    const homeLinks = screen.getAllByRole('link', { name: /home/i });
    fireEvent.click(homeLinks[homeLinks.length - 1]);
    expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
  });

  it('nav links point to the correct paths', () => {
    mockNavAuth.currentUser = 'Alice';
    renderNavbar();
    expect(screen.getByRole('link', { name: 'Duties' })).toHaveAttribute('href', '/duties');
    expect(screen.getByRole('link', { name: 'Sections' })).toHaveAttribute('href', '/sections');
    expect(screen.getByRole('link', { name: 'Devos Feedback' })).toHaveAttribute(
      'href',
      '/react/devos-feedback'
    );
  });

  describe('theme toggle', () => {
    it('renders theme toggle buttons (desktop and mobile)', () => {
      mockNavAuth.currentUser = 'Alice';
      renderNavbar();
      const toggleBtns = screen.getAllByRole('button', { name: 'Switch to dark mode' });
      expect(toggleBtns.length).toBeGreaterThanOrEqual(1);
    });

    it('renders theme toggle button in mobile menu', () => {
      mockNavAuth.currentUser = 'Alice';
      renderNavbar();
      const toggleBtns = screen.getAllByRole('button', { name: /switch to dark mode/i });
      expect(toggleBtns.length).toBeGreaterThanOrEqual(2);
    });

    it('desktop toggle switches to dark mode', () => {
      mockNavAuth.currentUser = 'Alice';
      renderNavbar();
      const toggleBtns = screen.getAllByRole('button', { name: 'Switch to dark mode' });
      fireEvent.click(toggleBtns[0]);
      expect(document.documentElement).toHaveAttribute('data-theme', 'dark');
      expect(screen.getAllByRole('button', { name: 'Switch to light mode' }).length).toBeGreaterThan(0);
    });

    it('toggle switches back to light mode', () => {
      mockNavAuth.currentUser = 'Alice';
      localStorage.setItem('theme', 'dark');
      renderNavbar();
      const toggleBtns = screen.getAllByRole('button', { name: 'Switch to light mode' });
      fireEvent.click(toggleBtns[0]);
      expect(document.documentElement).toHaveAttribute('data-theme', 'light');
    });

    it('theme toggle is not rendered when not logged in', () => {
      mockNavAuth.currentUser = null;
      renderNavbar();
      expect(screen.queryByRole('button', { name: /switch to/i })).toBeNull();
    });

    it('persists theme choice to localStorage', () => {
      mockNavAuth.currentUser = 'Alice';
      renderNavbar();
      const toggleBtn = screen.getAllByRole('button', { name: 'Switch to dark mode' })[0];
      fireEvent.click(toggleBtn);
      expect(localStorage.getItem('theme')).toBe('dark');
    });
  });
});
