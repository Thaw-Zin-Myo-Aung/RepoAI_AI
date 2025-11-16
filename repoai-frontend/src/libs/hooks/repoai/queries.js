// src/libs/hooks/repoai/queries.js
// RepoAI-specific queries using the repoai client

import { ENDPOINTS } from "../../api/endpoints";
import { useRepoGetQuery, REPOAI_BASE_URL } from "../../api/repoai";
import { useEffect, useState, useRef, useMemo } from "react";

const DEFAULT_OPTIONS = { staleTime: 5000, refetchOnWindowFocus: false };
const DEFAULT_NAMED_EVENTS = ["close", "end", "done", "finished", "complete"];

/**
 * Health check for the RepoAI service.
 * Calls GET /api/health on the RepoAI backend.
 * Usage: const { data, isLoading } = useRepoHealthCheck();
 */
export function useRepoHealthCheck(options = {}) {
  // endpoint here is 'api/health' per request
  return useRepoGetQuery("api/health", undefined, {
    ...DEFAULT_OPTIONS,
    ...options,
  });
}

/**
 * Simple GET hook for the SSE endpoint (non-streaming).
 * Calls GET /api/refactor/{sessionId}/sse and returns the response via React Query.
 * This does NOT open an EventSource; it is a single HTTP request useful for quick probes.
 *
 * Usage:
 * const { data, isLoading, error } = useRefactorSSEGet(sessionId, { enabled: !!sessionId });
 */
export function useRefactorSSEGet(sessionId, options = {}) {
  const endpoint = sessionId ? ENDPOINTS.REPOAI.REFACTOR_SSE(sessionId) : `api/refactor/no-session/sse`;
  return useRepoGetQuery(endpoint, undefined, {
    ...DEFAULT_OPTIONS,
    ...options,
    enabled: !!sessionId && (options.enabled !== false),
  });
}

/**
 * Streaming SSE hook using EventSource.
 * Opens a live connection to GET /api/refactor/{sessionId}/sse and emits each
 * message via onMessage as soon as it's received.
 *
 * Usage:
 * const { connected, lastEvent, error, close } = useRefactorSSE(sessionId, {
 *   enabled: !!sessionId,
 *   onMessage: (data) => console.log(data),
 *   onOpen: () => console.log('SSE open'),
 *   onError: (e) => console.warn('SSE error', e),
 *   onClose: () => console.log('SSE closed'),
 * });
 */
export function useRefactorSSE(
  sessionId,
  {
    onMessage,
    onOpen,
    onError,
    onClose,
    enabled = true,
    isTerminalEvent,
    retry = { enabled: true, maxAttempts: 5, initialDelayMs: 1000 },
    idleTimeoutMs,
    eventTypes = DEFAULT_NAMED_EVENTS,
    closeOnError = false,
    messageEventTypes = ["progress"],
  } = {}
) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const [error, setError] = useState(null);
  const [closed, setClosed] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const esRef = useRef(null);
  const attemptsRef = useRef(0);
  const retryTimerRef = useRef(null);
  const idleTimerRef = useRef(null);
  const readyStateRef = useRef(0); // 0: CONNECTING, 1: OPEN, 2: CLOSED
  const openedAtRef = useRef(0);

  // Keep callback refs stable to avoid re-opening on each render
  const onMessageRef = useRef(onMessage);
  const onOpenRef = useRef(onOpen);
  const onErrorRef = useRef(onError);
  const onCloseRef = useRef(onClose);
  const terminalCheckRef = useRef(isTerminalEvent);
  const eventTypesRef = useRef(eventTypes || DEFAULT_NAMED_EVENTS);
  const messageEventTypesRef = useRef(messageEventTypes || ["progress"]);
  useEffect(() => { onMessageRef.current = onMessage; }, [onMessage]);
  useEffect(() => { onOpenRef.current = onOpen; }, [onOpen]);
  useEffect(() => { onErrorRef.current = onError; }, [onError]);
  useEffect(() => { onCloseRef.current = onClose; }, [onClose]);
  useEffect(() => { terminalCheckRef.current = isTerminalEvent; }, [isTerminalEvent]);
  // Update named events ref only when the serialized list changes to avoid effect churn
  const eventsKey = useMemo(() => JSON.stringify(eventTypes || DEFAULT_NAMED_EVENTS), [eventTypes]);
  const msgEventsKey = useMemo(() => JSON.stringify(messageEventTypes || ["progress"]), [messageEventTypes]);
  useEffect(() => {
    try { eventTypesRef.current = JSON.parse(eventsKey); } catch { eventTypesRef.current = DEFAULT_NAMED_EVENTS; }
  }, [eventsKey]);
  useEffect(() => {
    try { messageEventTypesRef.current = JSON.parse(msgEventsKey); } catch { messageEventTypesRef.current = ["progress"]; }
  }, [msgEventsKey]);

  const defaultTerminalCheck = (e) => {
    if (!e) return false;
    if (typeof e === 'string') {
      const s = e.toLowerCase();
      return ['end','done','complete','finished','closed'].includes(s);
    }
    const status = (e.status && String(e.status).toLowerCase()) || '';
    const eventType = (e.event && String(e.event).toLowerCase()) || '';
    const stage = (e.stage && String(e.stage).toLowerCase()) || '';
    const progress = Number(e.progress ?? e.pct ?? -1);
    if ([
      'completed','complete','done','finished','failed','error','canceled','cancelled','terminated','closed',
    ].includes(status)) return true;
    if (['end','done','complete','finished','close','closed'].includes(eventType)) return true;
    if (['complete','completed','final','finalized','stopped','closed'].includes(stage)) return true;
    if (!Number.isNaN(progress) && progress >= 100) return true;
    return false;
  };

  useEffect(() => {
    if (!enabled) return undefined;
    if (!sessionId) return undefined;

    const endpoint = ENDPOINTS.REPOAI.REFACTOR_SSE(sessionId);
    const url = `${REPOAI_BASE_URL.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`;

    const emitClose = (reason = 'unknown', rawEvent) => {
      try { if (esRef.current) esRef.current.close(); } catch (_) {}
      esRef.current = null;
      readyStateRef.current = 2;
      setConnected(false);
      setClosed(true);
      setReconnecting(false);
      if (typeof onCloseRef.current === 'function') {
        try {
          onCloseRef.current({ reason, lastEvent }, rawEvent);
        } catch (_) {}
      }
    };

    const resetIdleTimer = () => {
      if (!idleTimeoutMs) return;
      if (idleTimerRef.current) clearTimeout(idleTimerRef.current);
      idleTimerRef.current = setTimeout(() => {
        emitClose('idle-timeout');
      }, idleTimeoutMs);
    };

    const open = () => {
      const es = new EventSource(url);
      esRef.current = es;
      setReconnecting(false);
      readyStateRef.current = 0;

      es.onopen = (ev) => {
        setConnected(true);
        setError(null);
        openedAtRef.current = Date.now();
        if (typeof onOpenRef.current === 'function') onOpenRef.current(ev);
        readyStateRef.current = 1;
        resetIdleTimer();
      };

      // Listen for named SSE events that often indicate stream termination
      const namedEventHandler = (evt) => {
        let parsed = evt.data;
        try { parsed = JSON.parse(evt.data); } catch (_) {}
        setLastEvent(parsed);
        // Treat these events as terminal by default
        emitClose('named-event', evt);
      };
      try {
        (eventTypesRef.current || []).forEach((t) => {
          if (t && typeof es.addEventListener === 'function') {
            es.addEventListener(t, namedEventHandler);
          }
        });
      } catch (_) {}

      // Listen for message-carrying custom events (e.g., 'progress') and forward to onMessage
      const passthroughHandler = (evt) => {
        let parsed = evt.data;
        try { parsed = JSON.parse(evt.data); } catch (_) {}
        setLastEvent(parsed);
        if (typeof onMessageRef.current === 'function') onMessageRef.current(parsed, evt);
        resetIdleTimer();
      };
      try {
        (messageEventTypesRef.current || []).forEach((t) => {
          // Avoid double-binding if terminal list also contains this type
          if (t && typeof es.addEventListener === 'function' && !(eventTypesRef.current || []).includes(t)) {
            es.addEventListener(t, passthroughHandler);
          }
        });
      } catch (_) {}

      es.onmessage = (evt) => {
        let parsed = evt.data;
        try { parsed = JSON.parse(evt.data); } catch (_) {}
        setLastEvent(parsed);
        if (typeof onMessageRef.current === 'function') onMessageRef.current(parsed, evt);
        resetIdleTimer();
        // Successful message after being open for a bit clears failure attempts
        const elapsed = Date.now() - (openedAtRef.current || Date.now());
        if (elapsed > 5000) {
          attemptsRef.current = 0;
        }

        try {
          const tc = terminalCheckRef.current;
          const terminalCheck = typeof tc === 'function' ? tc : defaultTerminalCheck;
          if (terminalCheck(parsed)) {
            emitClose('terminal-event', evt);
          }
        } catch (_) {}
      };

      es.onerror = (ev) => {
        setConnected(false);
        if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }
        const isClosed = es.readyState === 2; // EventSource.CLOSED
        if (isClosed) {
          emitClose('server-closed', ev);
        } else if (retry?.enabled && attemptsRef.current < (retry?.maxAttempts ?? 0)) {
          const elapsed = Date.now() - (openedAtRef.current || Date.now());
          // Count as a failure if the connection flapped quickly (<5s)
          if (elapsed < 5000) {
            attemptsRef.current += 1;
          } else {
            attemptsRef.current = 0;
          }
          const delay = (retry?.initialDelayMs ?? 1000) * Math.pow(2, attemptsRef.current);
          setReconnecting(true);
          try { if (esRef.current) esRef.current.close(); } catch (_) {}
          esRef.current = null;
          if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
          retryTimerRef.current = setTimeout(() => { open(); }, delay);
        } else {
          // No retry configured or retry attempts exhausted: explicitly close to stop native auto-reconnect
          const reason = (retry?.enabled === false) ? 'error-no-retry' : 'retry-exhausted';
          emitClose(reason, ev);
        }
        setError(new Error('SSE connection error'));
        if (typeof onErrorRef.current === 'function') onErrorRef.current(ev);
      };
    };

    open();

    return () => {
      if (retryTimerRef.current) { clearTimeout(retryTimerRef.current); retryTimerRef.current = null; }
      if (idleTimerRef.current) { clearTimeout(idleTimerRef.current); idleTimerRef.current = null; }
      if (esRef.current) {
        try { esRef.current.close(); } catch (_) {}
        esRef.current = null;
      }
      setConnected(false);
      setClosed(true);
      setReconnecting(false);
    };
  }, [sessionId, enabled, idleTimeoutMs, retry?.enabled, retry?.maxAttempts, retry?.initialDelayMs, closeOnError, msgEventsKey]);

  const close = () => {
    const es = esRef.current;
    if (es) {
      emitClose('manual');
    }
  };

  return { connected, lastEvent, error, close, closed, reconnecting };
}

/**
 * React Query based streaming SSE consumer using fetch ReadableStream.
 * It incrementally updates the query cache with parsed SSE events and resolves when stream ends.
 *
 * Returns the standard useQuery result plus a stop() helper to cancel.
 * Data shape: an array of parsed events (JSON if possible, else strings)
 */
// Note: previously there was a React Query based streaming helper here. It was removed per request.

/**
 * Subscribe to refactor SSE stream for a refactor session.
 * Usage: const { connected, lastEvent, error, close } = useRefactorSSE(sessionId, { onMessage })
 *
 * onMessage will be called with parsed data for each message.
 */


// export function useRefactorSSEProbe(sessionId, options = {}) {
//   return useRepoGetQuery(ENDPOINTS.REPOAI.REFACTOR_SSE(sessionId), undefined, {
//     ...DEFAULT_OPTIONS,
//     ...options,
//   });
// }

export default { useRepoHealthCheck, useRefactorSSEGet };
