import { render, screen } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';

import { VirtualizedList } from './VirtualizedList';

describe('VirtualizedList', () => {
  const originalOffsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
  const originalOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');

  afterEach(() => {
    if (originalOffsetHeight) {
      Object.defineProperty(HTMLElement.prototype, 'offsetHeight', originalOffsetHeight);
    }
    if (originalOffsetWidth) {
      Object.defineProperty(HTMLElement.prototype, 'offsetWidth', originalOffsetWidth);
    }
  });

  it('does not render-loop when getItemKey is provided', () => {
    Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 800 });
    Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 800 });

    render(
      <VirtualizedList
        items={[{ id: 'a' }, { id: 'b' }]}
        getItemKey={(item) => item.id}
        renderItem={(item) => <div>{item.id}</div>}
        estimatedSize={40}
        overscan={1}
      />
    );

    expect(screen.getByText('a')).toBeInTheDocument();
  });
});

