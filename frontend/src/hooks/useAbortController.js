import { useRef, useCallback, useEffect } from 'react';

/**
 * Custom hook for managing AbortController instances.
 * Prevents stale API responses from overwriting fresh data when:
 * - User navigates away and back
 * - Multiple rapid requests are made
 * - Component unmounts during pending request
 *
 * Feature #193: Late API response doesn't show stale data
 */
export function useAbortController() {
  const abortControllerRef = useRef(null);

  // Create a new AbortController, cancelling any previous one
  const createController = useCallback(() => {
    // Cancel previous request if still pending
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;
    return controller;
  }, []);

  // Get the current signal (for passing to fetch/axios)
  const getSignal = useCallback(() => {
    return abortControllerRef.current?.signal;
  }, []);

  // Cancel the current request
  const cancel = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return { createController, getSignal, cancel };
}

/**
 * Custom hook that provides a request ID mechanism to detect stale responses.
 * Simpler alternative to AbortController for cases where we just need to
 * ignore outdated responses rather than cancel them.
 *
 * Feature #193: Late API response doesn't show stale data
 */
export function useLatestRequest() {
  const requestIdRef = useRef(0);

  // Generate a new request ID (increments counter)
  const getRequestId = useCallback(() => {
    requestIdRef.current += 1;
    return requestIdRef.current;
  }, []);

  // Check if a given request ID is still the latest
  const isLatest = useCallback((requestId) => {
    return requestId === requestIdRef.current;
  }, []);

  // Reset (e.g., on unmount)
  const reset = useCallback(() => {
    requestIdRef.current = 0;
  }, []);

  useEffect(() => {
    return () => {
      // Increment on unmount to invalidate any pending callbacks
      requestIdRef.current += 1;
    };
  }, []);

  return { getRequestId, isLatest, reset };
}
