/**
 * MarkdownReport Component
 *
 * A styled markdown renderer optimized for Strategic Intelligence Reports.
 * Provides consistent, beautiful rendering of research reports with support
 * for GFM (GitHub Flavored Markdown) including tables, task lists, and more.
 *
 * @module CardDetail/MarkdownReport
 */

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { cn } from '../../lib/utils';

export interface MarkdownReportProps {
  /** The markdown content to render */
  content: string;
  /** Optional additional CSS classes */
  className?: string;
  /** Maximum height with overflow scroll (default: no max) */
  maxHeight?: string;
}

/**
 * MarkdownReport - Renders markdown with enhanced styling for strategic reports
 *
 * Features:
 * - GitHub Flavored Markdown support (tables, task lists, strikethrough)
 * - Styled headers with visual hierarchy
 * - Proper list formatting with nested support
 * - Table styling with alternating row colors
 * - Code block and inline code styling
 * - Blockquote styling
 * - Link styling with external link handling
 * - Dark mode support
 * - Responsive design
 */
export const MarkdownReport: React.FC<MarkdownReportProps> = ({
  content,
  className,
  maxHeight,
}) => {
  return (
    <div
      className={cn(
        'prose prose-sm dark:prose-invert max-w-none break-words',
        'prose-headings:text-gray-900 dark:prose-headings:text-white',
        'prose-p:text-gray-700 dark:prose-p:text-gray-300 prose-p:leading-relaxed',
        'prose-strong:text-gray-900 dark:prose-strong:text-white prose-strong:font-semibold',
        'prose-a:text-brand-blue hover:prose-a:text-brand-dark-blue prose-a:no-underline hover:prose-a:underline',
        maxHeight && `max-h-[${maxHeight}] overflow-y-auto`,
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Main title (# Header)
          h1: ({ node: _node, ...props }) => (
            <h1
              {...props}
              className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-white mt-6 mb-4 pb-2 border-b-2 border-brand-blue/30"
            />
          ),
          // Section headers (## Header)
          h2: ({ node: _node, ...props }) => (
            <h2
              {...props}
              className="text-lg sm:text-xl font-bold text-gray-900 dark:text-white mt-8 mb-3 pb-2 border-b border-gray-200 dark:border-gray-700 flex items-center gap-2"
            />
          ),
          // Subsection headers (### Header)
          h3: ({ node: _node, ...props }) => (
            <h3
              {...props}
              className="text-base sm:text-lg font-semibold text-gray-800 dark:text-gray-100 mt-6 mb-2"
            />
          ),
          // Minor headers (#### Header)
          h4: ({ node: _node, ...props }) => (
            <h4
              {...props}
              className="text-sm sm:text-base font-semibold text-gray-800 dark:text-gray-200 mt-4 mb-2"
            />
          ),
          // Paragraphs
          p: ({ node: _node, ...props }) => (
            <p
              {...props}
              className="text-gray-700 dark:text-gray-300 mb-4 text-sm sm:text-base leading-relaxed"
            />
          ),
          // Unordered lists
          ul: ({ node: _node, ...props }) => (
            <ul
              {...props}
              className="list-disc pl-5 mb-4 space-y-1.5 text-gray-700 dark:text-gray-300"
            />
          ),
          // Ordered lists
          ol: ({ node: _node, ...props }) => (
            <ol
              {...props}
              className="list-decimal pl-5 mb-4 space-y-1.5 text-gray-700 dark:text-gray-300"
            />
          ),
          // List items
          li: ({ node: _node, children, ...props }) => (
            <li
              {...props}
              className="text-gray-700 dark:text-gray-300 text-sm sm:text-base leading-relaxed pl-1"
            >
              {children}
            </li>
          ),
          // Links
          a: ({ node: _node, href, children, ...props }) => (
            <a
              {...props}
              href={href}
              className="text-brand-blue hover:text-brand-dark-blue dark:text-brand-light-blue dark:hover:text-white underline decoration-brand-blue/30 hover:decoration-brand-blue transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          // Inline code
          code: ({ node: _node, className, children, ...props }) => {
            const isCodeBlock = className?.includes('language-');
            if (isCodeBlock) {
              return (
                <code
                  {...props}
                  className={cn(
                    'block bg-gray-900 dark:bg-gray-950 text-gray-100 p-4 rounded-lg text-xs sm:text-sm overflow-x-auto',
                    className
                  )}
                >
                  {children}
                </code>
              );
            }
            return (
              <code
                {...props}
                className="bg-gray-100 dark:bg-gray-800 text-brand-dark-blue dark:text-brand-light-blue px-1.5 py-0.5 rounded text-xs sm:text-sm font-mono"
              >
                {children}
              </code>
            );
          },
          // Code blocks (pre wrapper)
          pre: ({ node: _node, ...props }) => (
            <pre
              {...props}
              className="bg-gray-900 dark:bg-gray-950 rounded-lg overflow-x-auto mb-4 text-sm"
            />
          ),
          // Blockquotes
          blockquote: ({ node: _node, ...props }) => (
            <blockquote
              {...props}
              className="border-l-4 border-brand-blue pl-4 py-2 my-4 bg-brand-light-blue/10 dark:bg-brand-blue/10 rounded-r-lg italic text-gray-700 dark:text-gray-300"
            />
          ),
          // Tables
          table: ({ node: _node, ...props }) => (
            <div className="overflow-x-auto mb-4 rounded-lg border border-gray-200 dark:border-gray-700">
              <table
                {...props}
                className="min-w-full divide-y divide-gray-200 dark:divide-gray-700 text-sm"
              />
            </div>
          ),
          // Table header
          thead: ({ node: _node, ...props }) => (
            <thead
              {...props}
              className="bg-gray-50 dark:bg-gray-800"
            />
          ),
          // Table body
          tbody: ({ node: _node, ...props }) => (
            <tbody
              {...props}
              className="divide-y divide-gray-200 dark:divide-gray-700 bg-white dark:bg-gray-900"
            />
          ),
          // Table rows
          tr: ({ node: _node, ...props }) => (
            <tr
              {...props}
              className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
            />
          ),
          // Table header cells
          th: ({ node: _node, ...props }) => (
            <th
              {...props}
              className="px-3 py-2 text-left text-xs font-semibold text-gray-700 dark:text-gray-200 uppercase tracking-wider"
            />
          ),
          // Table data cells
          td: ({ node: _node, ...props }) => (
            <td
              {...props}
              className="px-3 py-2 text-gray-700 dark:text-gray-300"
            />
          ),
          // Horizontal rule
          hr: ({ node: _node, ...props }) => (
            <hr
              {...props}
              className="my-6 border-t-2 border-gray-200 dark:border-gray-700"
            />
          ),
          // Strong/bold text
          strong: ({ node: _node, ...props }) => (
            <strong
              {...props}
              className="font-semibold text-gray-900 dark:text-white"
            />
          ),
          // Emphasis/italic text
          em: ({ node: _node, ...props }) => (
            <em
              {...props}
              className="italic text-gray-700 dark:text-gray-300"
            />
          ),
          // Images
          img: ({ node: _node, alt, ...props }) => (
            <img
              {...props}
              alt={alt}
              className="rounded-lg shadow-md max-w-full h-auto my-4"
              loading="lazy"
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownReport;
