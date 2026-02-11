/**
 * useKeywordSuggestions Hook
 *
 * Manages AI keyword suggestion state and fetching for workstream forms.
 * Accepts callbacks for getting topic context and auth tokens to remain
 * decoupled from form state management.
 */

import { useState, useCallback } from "react";
import { suggestKeywords } from "../lib/discovery-api";

export function useKeywordSuggestions(
  getTopicContext: () => {
    name: string;
    description: string;
    keywords: string[];
  },
  getAuthToken: () => Promise<string | undefined>,
) {
  const [suggestedKeywords, setSuggestedKeywords] = useState<string[]>([]);
  const [isSuggestingKeywords, setIsSuggestingKeywords] = useState(false);

  const handleSuggestKeywords = useCallback(
    async (topicOverride?: string) => {
      const ctx = getTopicContext();
      const topic =
        topicOverride?.trim() || ctx.name.trim() || ctx.description.trim();
      if (!topic) return;

      setIsSuggestingKeywords(true);
      setSuggestedKeywords([]);
      try {
        const token = await getAuthToken();
        if (!token) return;
        const result = await suggestKeywords(topic, token);
        const newSuggestions = result.suggestions.filter(
          (kw) => !ctx.keywords.includes(kw),
        );
        setSuggestedKeywords(newSuggestions);
      } catch (error) {
        console.error("Failed to suggest keywords:", error);
      } finally {
        setIsSuggestingKeywords(false);
      }
    },
    [getTopicContext, getAuthToken],
  );

  const removeSuggestion = useCallback((keyword: string) => {
    setSuggestedKeywords((prev) => prev.filter((kw) => kw !== keyword));
  }, []);

  return {
    suggestedKeywords,
    isSuggestingKeywords,
    handleSuggestKeywords,
    removeSuggestion,
    setSuggestedKeywords,
  };
}
