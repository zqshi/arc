import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import MarkdownContent from './MarkdownContent';

describe('MarkdownContent', () => {
  it('renders plain text', () => {
    const { container } = render(<MarkdownContent content="Hello world" />);
    expect(container.textContent).toContain('Hello world');
  });

  it('renders bold text', () => {
    const { container } = render(<MarkdownContent content="**bold text**" />);
    const strong = container.querySelector('strong');
    expect(strong).toBeTruthy();
    expect(strong?.textContent).toBe('bold text');
  });

  it('renders empty content without error', () => {
    const { container } = render(<MarkdownContent content="" />);
    expect(container).toBeTruthy();
  });

  it('renders inline code', () => {
    const { container } = render(<MarkdownContent content="Use `const` keyword" />);
    const code = container.querySelector('code');
    expect(code).toBeTruthy();
    expect(code?.textContent).toBe('const');
  });

  it('renders links', () => {
    const { container } = render(<MarkdownContent content="[Link](https://example.com)" />);
    const link = container.querySelector('a');
    expect(link).toBeTruthy();
    expect(link?.getAttribute('href')).toBe('https://example.com');
  });
});
