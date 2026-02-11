/**
 * NotesTab Component
 *
 * Displays the Notes tab for a card, including:
 * - Add note form with textarea and submit button
 * - Notes list with timestamps and private badges
 * - Empty state when no notes exist
 *
 * @module CardDetail/tabs/NotesTab
 */

import React from 'react';
import { TrendingUp } from 'lucide-react';
import type { Note } from '../types';

/**
 * Props for the NotesTab component
 */
export interface NotesTabProps {
  /**
   * Array of notes to display
   */
  notes: Note[];

  /**
   * Current value of the new note textarea
   */
  newNoteValue: string;

  /**
   * Callback when new note value changes
   */
  onNewNoteChange: (value: string) => void;

  /**
   * Callback when add note button is clicked
   */
  onAddNote: () => void;

  /**
   * Optional custom CSS class name for the container
   */
  className?: string;
}

/**
 * NotesTab displays the notes panel for a card with add note form and notes list.
 *
 * Features:
 * - Add note form with textarea and submit button
 * - Notes list with card-style items
 * - Private note badges
 * - Responsive design with different layouts for mobile/desktop
 * - Dark mode support
 * - Hover effects with translation and border accent
 * - Empty state with helpful message
 *
 * @example
 * ```tsx
 * const [newNote, setNewNote] = useState('');
 * const [notes, setNotes] = useState<Note[]>([]);
 *
 * const handleAddNote = async () => {
 *   // Add note to database
 *   const note = await addNoteToCard(cardId, newNote);
 *   setNotes([note, ...notes]);
 *   setNewNote('');
 * };
 *
 * <NotesTab
 *   notes={notes}
 *   newNoteValue={newNote}
 *   onNewNoteChange={setNewNote}
 *   onAddNote={handleAddNote}
 * />
 * ```
 */
export const NotesTab: React.FC<NotesTabProps> = ({
  notes,
  newNoteValue,
  onNewNoteChange,
  onAddNote,
  className = '',
}) => {
  return (
    <div className={`space-y-4 sm:space-y-6 ${className}`}>
      {/* Add Note Form */}
      <div className="bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Add Note
        </h3>
        <div className="space-y-4">
          <textarea
            rows={3}
            className="block w-full border-gray-300 dark:border-gray-600 dark:bg-dark-surface-elevated dark:text-white rounded-md shadow-sm focus:ring-brand-blue focus:border-brand-blue sm:text-sm"
            placeholder="Add your thoughts and analysis..."
            value={newNoteValue}
            onChange={(e) => onNewNoteChange(e.target.value)}
            aria-label="New note content"
          />
          <button
            onClick={onAddNote}
            disabled={!newNoteValue.trim()}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-brand-blue hover:bg-brand-dark-blue focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-blue disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            aria-label="Add note"
          >
            Add Note
          </button>
        </div>
      </div>

      {/* Notes List */}
      <div className="space-y-4">
        {notes.length === 0 ? (
          <EmptyNotesState />
        ) : (
          notes.map((note) => (
            <NoteCard key={note.id} note={note} />
          ))
        )}
      </div>
    </div>
  );
};

/**
 * Props for the NoteCard component
 */
interface NoteCardProps {
  /**
   * The note to display
   */
  note: Note;
}

/**
 * NoteCard displays a single note with content, timestamp, and privacy badge.
 *
 * Features:
 * - Card-style display with shadow and rounded corners
 * - Hover effect with translation and accent border
 * - Responsive layout for timestamp and badge
 * - Dark mode support
 */
const NoteCard: React.FC<NoteCardProps> = ({ note }) => {
  return (
    <div
      className="bg-white dark:bg-dark-surface rounded-lg shadow p-4 sm:p-6 border-l-4 border-transparent transition-all duration-200 hover:-translate-y-1 hover:shadow-lg hover:border-l-brand-blue"
    >
      <p className="text-gray-700 dark:text-gray-300 mb-3 break-words">
        {note.content}
      </p>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-sm text-gray-500 dark:text-gray-400">
        <span className="text-xs sm:text-sm">
          {new Date(note.created_at).toLocaleString()}
        </span>
        {note.is_private && <PrivateBadge />}
      </div>
    </div>
  );
};

/**
 * PrivateBadge displays a badge indicating the note is private.
 */
const PrivateBadge: React.FC = () => {
  return (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
      Private
    </span>
  );
};

/**
 * EmptyNotesState displays when there are no notes.
 *
 * Features:
 * - Centered layout with icon
 * - Helpful message encouraging user to add first note
 * - Dark mode support
 */
const EmptyNotesState: React.FC = () => {
  return (
    <div className="text-center py-12 bg-white dark:bg-dark-surface rounded-lg shadow">
      <TrendingUp className="mx-auto h-12 w-12 text-gray-400" aria-hidden="true" />
      <h3 className="mt-2 text-sm font-medium text-gray-900 dark:text-white">
        No notes yet
      </h3>
      <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Add your first note to start tracking your insights.
      </p>
    </div>
  );
};

export default NotesTab;
