/**
 * Unit-Tests für App-Komponente.
 * 
 * Testet Rendering der Root-Komponente und Layout.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../src/App';

describe('App Component', () => {
  it('sollte Seitenkopf mit Titel rendern', () => {
    render(<App />);

    const title = screen.getByRole('heading', { level: 1 });
    expect(title).toHaveTextContent('Crypto Trading Board');
  });

  it('sollte Main-Element mit ChartDemo rendieren', () => {
    render(<App />);

    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
  });

  it('sollte Seitenkopf vor Main-Inhalt rendern', () => {
    const { container } = render(<App />);

    const header = container.querySelector('header.page-header');
    const main = container.querySelector('main.main');

    expect(header).toBeInTheDocument();
    expect(main).toBeInTheDocument();

    // Header sollte vor Main im DOM sein
    expect(header.compareDocumentPosition(main)).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING
    );
  });
});
