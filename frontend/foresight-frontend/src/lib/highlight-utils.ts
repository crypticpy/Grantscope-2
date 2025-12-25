import React from 'react';

/**
 * Escapes special characters in a string for use in a regular expression
 */
function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Highlights matching keywords in text by wrapping them in React elements
 *
 * @param text - The text to search within
 * @param keywords - Space-separated keywords to highlight
 * @param highlightClassName - CSS class to apply to highlighted portions
 * @returns React nodes with highlighted portions wrapped in mark elements
 */
export function highlightText(
  text: string,
  keywords: string,
  highlightClassName: string = 'bg-yellow-200 dark:bg-yellow-700 px-0.5 rounded'
): React.ReactNode {
  // If no keywords or empty text, return the original text
  if (!keywords.trim() || !text) {
    return text;
  }

  // Split keywords by spaces and filter out empty strings
  const keywordList = keywords
    .trim()
    .split(/\s+/)
    .filter(k => k.length > 0)
    .map(k => escapeRegExp(k));

  // If no valid keywords after filtering, return original text
  if (keywordList.length === 0) {
    return text;
  }

  // Create a regex pattern that matches any of the keywords (case-insensitive)
  const pattern = new RegExp(`(${keywordList.join('|')})`, 'gi');

  // Split the text by the pattern, keeping the matched portions
  const parts = text.split(pattern);

  // If no matches found (parts length is 1), return original text
  if (parts.length === 1) {
    return text;
  }

  // Map parts to React elements, highlighting matches
  return parts.map((part, index) => {
    // Check if this part matches any keyword (case-insensitive)
    const isMatch = keywordList.some(
      keyword => part.toLowerCase() === keyword.toLowerCase()
    );

    if (isMatch) {
      return React.createElement(
        'mark',
        { key: index, className: highlightClassName },
        part
      );
    }

    return part;
  });
}

/**
 * Creates a highlighted text component using the highlightText utility
 * This is a convenience function for common use cases
 */
export function createHighlightedText(
  text: string,
  searchQuery: string
): React.ReactNode {
  return highlightText(text, searchQuery);
}
