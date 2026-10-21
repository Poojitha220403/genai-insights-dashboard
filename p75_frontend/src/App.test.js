import { render, screen } from '@testing-library/react';
import App from './App';

// d3 v7 ships ES modules that CRA's Jest doesn't transpile; charts aren't rendered here
jest.mock('d3', () => ({}));

beforeEach(() => localStorage.clear());

test('logged-out visitors land on the welcome page with no app navbar', () => {
  render(<App />);
  expect(screen.getByText(/Pioneering the Future/i)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /logout/i })).not.toBeInTheDocument();
});
