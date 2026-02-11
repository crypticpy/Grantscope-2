import { useRef, useCallback, useEffect } from "react";
import {
  getWorkstreamScanStatus,
  type WorkstreamScanStatusResponse,
} from "../lib/workstream-api";

interface UseWorkstreamScanPollingArgs {
  workstreamId: string | undefined;
  getAuthToken: () => Promise<string | null>;
  onStatus?: (status: WorkstreamScanStatusResponse) => void;
  onComplete?: (status: WorkstreamScanStatusResponse) => Promise<void> | void;
  onError?: (message: string) => void;
  maxAttempts?: number;
  intervalMs?: number;
}

export function useWorkstreamScanPolling({
  workstreamId,
  getAuthToken,
  onStatus,
  onComplete,
  onError,
  maxAttempts = 200,
  intervalMs = 3000,
}: UseWorkstreamScanPollingArgs) {
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Use refs for callbacks so we don't need them as deps
  const onStatusRef = useRef(onStatus);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  // Keep refs up to date
  onStatusRef.current = onStatus;
  onCompleteRef.current = onComplete;
  onErrorRef.current = onError;

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPollingExistingScan = useCallback(
    async (scanId?: string) => {
      if (!workstreamId) return;

      const token = await getAuthToken();
      if (!token) return;

      try {
        // If no scanId provided, fetch the latest active scan
        const status = await getWorkstreamScanStatus(
          token,
          workstreamId,
          scanId,
        );
        if (!status) return;

        onStatusRef.current?.(status);

        // If scan already completed/failed (fast scan or slow navigation),
        // fire the completion callback immediately instead of polling.
        if (status.status === "completed" || status.status === "failed") {
          await onCompleteRef.current?.(status);
          return;
        }

        // Only poll if still active
        if (status.status !== "queued" && status.status !== "running") {
          return;
        }

        const activeScanId = status.scan_id;
        let attempts = 0;

        const poll = async () => {
          attempts++;
          if (attempts > maxAttempts) {
            stopPolling();
            onErrorRef.current?.(
              "Scan timed out. Check back later for results.",
            );
            return;
          }

          try {
            const freshToken = await getAuthToken();
            if (!freshToken) {
              stopPolling();
              return;
            }

            const current = await getWorkstreamScanStatus(
              freshToken,
              workstreamId,
              activeScanId,
            );
            onStatusRef.current?.(current);

            if (current.status === "completed" || current.status === "failed") {
              stopPolling();
              await onCompleteRef.current?.(current);
            }
          } catch (err) {
            console.error("Error polling scan status:", err);
          }
        };

        pollRef.current = setInterval(poll, intervalMs);
        poll(); // Immediately poll once
      } catch (err) {
        console.error("Error fetching initial scan status:", err);
      }
    },
    [workstreamId, getAuthToken, maxAttempts, intervalMs, stopPolling],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  return {
    startPollingExistingScan,
    stopPolling,
    isPolling: pollRef.current !== null,
  };
}
