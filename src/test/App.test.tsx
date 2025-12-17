import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

// Simple component for testing setup
const TestComponent = () => <div>Hello Abacus</div>;

describe('App', () => {
  it('renders correctly', () => {
    render(<TestComponent />);
    expect(screen.getByText('Hello Abacus')).toBeInTheDocument();
  });
});
