// src/libs/hooks/profile/queries.js
// Query hook to fetch and persist the current user profile.

import { useEffect } from "react";
import { useGetQuery } from "../../api/api";
import { ENDPOINTS } from "../../api/endpoints";
import { useUser } from "../../stores/useUser";

const DEFAULT_OPTIONS = {
  staleTime: 30_000,
  refetchOnWindowFocus: true,
};

// Check auth status endpoint (e.g., { authenticated: boolean, ... })
export function useProfile(options = {}) {
  const setUser = useUser((s) => s.setUser);
  const clearUser = useUser((s) => s.clearUser);

  const query = useGetQuery(ENDPOINTS.USER, undefined, {
    ...DEFAULT_OPTIONS,
    // keep compatibility if the core hook changes its default select
    select: (res) => res?.data ?? res,
    onError: (err) => {
      // On error (including 401), ensure store is cleared
      clearUser();
      if (typeof options.onError === "function") options.onError(err);
    },
    // Do not attach onSuccess here; we'll sync via useEffect so it also runs on cached data
    ...options,
  });

  // Sync the store whenever data changes (works for fresh fetches and cached data)
  useEffect(() => {
    const data = query.data;
    if (!data) return;
    const userObj = typeof data === "object" ? data.user ?? data : null;
    if (userObj && Object.keys(userObj).length > 0) {
      setUser(userObj);
    } else if (data && data.authenticated === false) {
      clearUser();
    }
  }, [query.data, setUser, clearUser]);

  return query;
}
