/**
 * useSpeechToText Hook
 *
 * Provides speech-to-text transcription using the Web Speech API.
 * Gracefully handles unsupported browsers by reporting `isSupported: false`.
 *
 * @module hooks/useSpeechToText
 */

import { useState, useRef, useCallback, useEffect } from "react";

// ============================================================================
// Types
// ============================================================================

export interface UseSpeechToTextReturn {
  /** Whether the microphone is currently recording */
  isListening: boolean;
  /** Whether the Web Speech API is available in this browser */
  isSupported: boolean;
  /** The latest transcribed text (final result only) */
  transcript: string;
  /** Begin a new speech recognition session */
  startListening: () => void;
  /** Stop the current speech recognition session */
  stopListening: () => void;
}

// Web Speech API types (not in standard TS lib)
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: { readonly transcript: string };
}

interface SpeechRecognitionResultList {
  readonly length: number;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionEvent {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}

interface SpeechRecognitionErrorEvent {
  readonly error: string;
}

interface SpeechRecognitionInstance {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEvent) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionInstance;

// ============================================================================
// Helpers
// ============================================================================

/**
 * Returns the SpeechRecognition constructor if available, or null.
 */
function getSpeechRecognition(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const w = window as Record<string, any>;
  return w.SpeechRecognition || w.webkitSpeechRecognition || null;
}

// ============================================================================
// Hook
// ============================================================================

export function useSpeechToText(): UseSpeechToTextReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const isSupported = getSpeechRecognition() !== null;

  /**
   * Start a fresh speech recognition session.
   * Each call creates a new recognition instance to avoid stale-state issues.
   */
  const startListening = useCallback(() => {
    const SpeechRecognition = getSpeechRecognition();
    if (!SpeechRecognition) return;

    // Stop any existing session first
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // Ignore — may already be stopped
      }
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let finalTranscript = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result && result.isFinal) {
          finalTranscript += result[0]?.transcript ?? "";
        }
      }

      // Only emit the final transcript so the input isn't flooded with partials
      if (finalTranscript) {
        setTranscript(finalTranscript);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // "aborted" and "no-speech" are expected — don't log them as errors
      if (event.error !== "aborted" && event.error !== "no-speech") {
        console.warn("[useSpeechToText] Recognition error:", event.error);
      }
      setIsListening(false);
      recognitionRef.current = null;
    };

    recognitionRef.current = recognition;
    setTranscript("");
    setIsListening(true);

    try {
      recognition.start();
    } catch (err) {
      console.warn("[useSpeechToText] Failed to start recognition:", err);
      setIsListening(false);
      recognitionRef.current = null;
    }
  }, []);

  /**
   * Stop the current recognition session gracefully.
   * `stop()` will trigger the `onend` callback and deliver any final results.
   */
  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // Ignore — may already be stopped
      }
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // Ignore
        }
        recognitionRef.current = null;
      }
    };
  }, []);

  return {
    isListening,
    isSupported,
    transcript,
    startListening,
    stopListening,
  };
}
