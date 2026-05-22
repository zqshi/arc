import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ToastProvider, useToast } from '../components/Toast';
import { act } from '@testing-library/react';

function TestConsumer() {
  const { toast } = useToast();
  return (
    <button onClick={() => toast('Hello', 'success')}>Fire</button>
  );
}

describe('Toast', () => {
  it('renders toast message when fired', async () => {
    render(
      <ToastProvider>
        <TestConsumer />
      </ToastProvider>,
    );

    await act(async () => {
      screen.getByText('Fire').click();
    });

    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('throws when useToast is used outside provider', () => {
    expect(() => {
      render(<TestConsumer />);
    }).toThrow('useToast must be used within ToastProvider');
  });
});
