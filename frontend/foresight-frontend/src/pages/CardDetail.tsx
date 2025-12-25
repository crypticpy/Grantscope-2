/**
 * CardDetail Page
 *
 * This page displays the detailed view of a single card/trend.
 * The actual component implementation is in components/CardDetail/.
 *
 * @module pages/CardDetail
 */

import React from 'react';
import { CardDetail as CardDetailComponent } from '../components/CardDetail';

/**
 * CardDetail page component.
 *
 * Renders the CardDetailComponent which displays comprehensive
 * information about a card/trend including:
 * - Header with title, badges, and summary
 * - Action buttons (Compare, Update, Deep Research, Export, Follow)
 * - Tab-based navigation (Overview, Sources, Timeline, Notes, Related)
 *
 * @example
 * ```tsx
 * // Route configuration
 * <Route path="/cards/:slug" element={<CardDetail />} />
 * ```
 */
const CardDetail: React.FC = () => {
  return <CardDetailComponent />;
};

export default CardDetail;
