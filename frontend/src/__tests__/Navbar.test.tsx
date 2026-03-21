import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Navbar from '../Navbar';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderNavbar() {
  return render(
    <MemoryRouter>
      <Navbar />
    </MemoryRouter>
  );
}

describe('Navbar', () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockClear();
  });

  it('renders nothing when no currentUser in localStorage', () => {
    const { container } = renderNavbar();
    expect(container.firstChild).toBeNull();
  });

  it('renders nav links when user is logged in', () => {
    localStorage.setItem('currentUser', 'Alice');
    renderNavbar();
    expect(screen.getByText('Ballyholme CSSM Helper')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Home' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Duties' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Devos Feedback' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Sections' })).toBeInTheDocument();
  });

  it('clicking logout clears currentUser and navigates to /login', () => {
    localStorage.setItem('currentUser', 'Alice');
    renderNavbar();
    fireEvent.click(screen.getAllByRole('button', { name: /logout/i })[0]);
    expect(localStorage.getItem('currentUser')).toBeNull();
    expect(mockNavigate).toHaveBeenCalledWith('/login');
  });

  it('mobile menu button toggles aria-expanded', () => {
    localStorage.setItem('currentUser', 'Alice');
    renderNavbar();
    const menuBtn = screen.getByRole('button', { name: /toggle navigation menu/i });
    expect(menuBtn).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(menuBtn);
    expect(menuBtn).toHaveAttribute('aria-expanded', 'true');
  });

  it('mobile menu closes after clicking a link', () => {
    localStorage.setItem('currentUser', 'Alice');
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
    localStorage.setItem('currentUser', 'Alice');
    renderNavbar();
    expect(screen.getByRole('link', { name: 'Duties' })).toHaveAttribute('href', '/duties');
    expect(screen.getByRole('link', { name: 'Sections' })).toHaveAttribute('href', '/sections');
    expect(screen.getByRole('link', { name: 'Devos Feedback' })).toHaveAttribute(
      'href',
      '/react/devos-feedback'
    );
  });
});
