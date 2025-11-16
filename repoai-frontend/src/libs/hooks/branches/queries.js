// src/libs/hooks/branches/queries.js
// Branches list & sync query hooks

import { useGetQuery } from '../../api/api';
import { ENDPOINTS } from '../../api/endpoints';
import { useQueryClient } from '@tanstack/react-query';

const DEFAULT_OPTIONS = {
  staleTime: 30_000,
  refetchOnWindowFocus: false,
};

/**
 * Fetch branches for a repository by repoId (id used by the API path).
 * Usage: const { data: branches, isLoading } = useBranchesList(repoId)
 */
export function useBranchesList(repoId, options = {}) {
  // Allow calling hook safely without repoId; useQuery will stay disabled until repoId is provided.
  const endpoint = repoId ? ENDPOINTS.BRANCHES.LIST(repoId) : '__branches_not_set__';
  return useGetQuery(endpoint, undefined, { enabled: !!repoId, ...DEFAULT_OPTIONS, ...options });
}

// NOTE: Sync-related hooks are implemented as mutations (POST) and live in
// `src/libs/hooks/branches/mutation.js` because sync typically changes server
// state. Keep queries focused on GET (read) operations only.
