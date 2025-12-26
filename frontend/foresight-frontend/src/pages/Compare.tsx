/**
 * Compare Page
 *
 * Renders the TrendComparisonView for comparing two cards side-by-side.
 * Card IDs are read from URL query params: /compare?card_ids=id1,id2
 */

import React from 'react';
import { TrendComparisonView } from '../components/visualizations/TrendComparisonView';

const Compare: React.FC = () => {
  const handleCardClick = (_cardId: string) => {
    // Could navigate to card detail, but for now just log
    // The TrendComparisonView already has links to card detail pages
  };

  return <TrendComparisonView onCardClick={handleCardClick} />;
};

export default Compare;
