/**
 * CardDetail Tab Components
 *
 * Tab content components for the CardDetail view.
 * Each tab component handles a specific section of the card details.
 *
 * @module CardDetail/tabs
 */

// Overview tab components
export * from './OverviewTab';

// Notes tab
export { NotesTab } from './NotesTab';
export type { NotesTabProps } from './NotesTab';

// Sources tab
export { SourcesTab } from './SourcesTab';
export type { SourcesTabProps } from './SourcesTab';

// Timeline tab
export { TimelineTab } from './TimelineTab';
export type { TimelineTabProps } from './TimelineTab';

// Related tab
export { RelatedTab } from './RelatedTab';
export type { RelatedTabProps } from './RelatedTab';
