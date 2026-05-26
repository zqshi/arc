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

function ErrorConsumer() {
  const { toast } = useToast();
  return (
    <button onClick={() => toast('Oops', 'error')}>FireError</button>
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

  it('uses role="status" for success toasts', async () => {
    render(
      <ToastProvider>
        <TestConsumer />
      </ToastProvider>,
    );

    await act(async () => {
      screen.getByText('Fire').click();
    });

    expect(screen.getByText('Hello').closest('[role="status"]')).toBeInTheDocument();
  });

  it('uses role="alert" for error toasts', async () => {
    render(
      <ToastProvider>
        <ErrorConsumer />
      </ToastProvider>,
    );

    await act(async () => {
      screen.getByText('FireError').click();
    });

    expect(screen.getByText('Oops').closest('[role="alert"]')).toBeInTheDocument();
  });

  it('throws when useToast is used outside provider', () => {
    expect(() => {
      render(<TestConsumer />);
    }).toThrow('useToast must be used within ToastProvider');
  });
});
