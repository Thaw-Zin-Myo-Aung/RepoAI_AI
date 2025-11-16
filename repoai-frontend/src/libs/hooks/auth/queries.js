// src/libs/auth/queries.js
// Centralized React Query hooks for authentication-related data.

import { useGetQuery } from '../../api/api';
import { ENDPOINTS } from '../../api/endpoints';

const DEFAULT_OPTIONS = {
  staleTime: 30_000,
  refetchOnWindowFocus: true,
};

// Check auth status endpoint (e.g., { authenticated: boolean, ... })
export function useAuthStatus(options = {}) {
  return useGetQuery(ENDPOINTS.AUTH.STATUS, undefined, { ...DEFAULT_OPTIONS, ...options });
}

// Current authenticated user profile (e.g., { username, ... })
export function useCurrentUser(options = {}) {
  return useGetQuery(ENDPOINTS.USER, undefined, { ...DEFAULT_OPTIONS, ...options });
}

// Initiate login endpoint via GET (note: many backends expect a browser redirect instead)
// Useful if your backend returns JSON with a login URL or status.
export function useAuthLogin(options = {}) {
  return useGetQuery(ENDPOINTS.AUTH.LOGIN, undefined, { ...DEFAULT_OPTIONS, ...options });
}

// Retrieve or validate a token via GET. If your backend expects POST for token exchange,
// consider using a mutation hook instead — this GET hook matches the request's ask.
// Usage: const { data, isLoading } = useAuthTokenQuery(params?)
export function useAuthTokenQuery(params, options = {}) {
  return useGetQuery(ENDPOINTS.AUTH.TOKEN, params, { ...DEFAULT_OPTIONS, ...options });
}
