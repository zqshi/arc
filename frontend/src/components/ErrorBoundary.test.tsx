import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import ErrorBoundary from './ErrorBoundary';

let shouldThrow = false;

function ConditionalThrow() {
  if (shouldThrow) throw new Error('test error');
  return <div>ok</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    shouldThrow = false;
    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText('ok')).toBeInTheDocument();
  });

  it('renders fallback on error', () => {
    shouldThrow = true;
    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText('页面出错了')).toBeInTheDocument();
    expect(screen.getByText('test error')).toBeInTheDocument();
  });

  it('recovers on reset via key-based remount', () => {
    shouldThrow = true;
    render(
      <ErrorBoundary>
        <ConditionalThrow />
      </ErrorBoundary>,
    );
    expect(screen.getByText('页面出错了')).toBeInTheDocument();

    shouldThrow = false;
    fireEvent.click(screen.getByText('重试'));
    expect(screen.getByText('ok')).toBeInTheDocument();
  });
});
