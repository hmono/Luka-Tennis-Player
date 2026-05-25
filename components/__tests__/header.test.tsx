// @vitest-environment jsdom
import '@testing-library/jest-dom';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import Header from '../ui/header';

// next/link renders an <a> tag in tests
vi.mock('next/link', () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) => (
    <a href={href} className={className}>{children}</a>
  ),
}));

describe('Header', () => {
  it('renders the brand link', () => {
    render(<Header />);
    expect(screen.getByText('Luka Ono Analytics')).toBeInTheDocument();
  });

  it('brand link points to /', () => {
    render(<Header />);
    const brand = screen.getByText('Luka Ono Analytics').closest('a');
    expect(brand).toHaveAttribute('href', '/');
  });

  it('renders all navigation links', () => {
    render(<Header />);
    expect(screen.getByText('Career')).toBeInTheDocument();
    expect(screen.getByText('Tactics')).toBeInTheDocument();
    expect(screen.getByText('Physical')).toBeInTheDocument();
    expect(screen.getByText('Level Comparison')).toBeInTheDocument();
    expect(screen.getByText('Analytics Modules')).toBeInTheDocument();
  });

  it('renders tagline with current month and year', () => {
    render(<Header />);
    const year = new Date().getFullYear().toString();
    const tagline = screen.getByText(/Performance intelligence partner/);
    expect(tagline.textContent).toContain(year);
  });

  it('Career nav link points to /career', () => {
    render(<Header />);
    const link = screen.getByText('Career').closest('a');
    expect(link).toHaveAttribute('href', '/career');
  });
});
