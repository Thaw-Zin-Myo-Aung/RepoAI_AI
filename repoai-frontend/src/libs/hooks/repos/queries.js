// src/libs/hooks/repos/queries.js
// Repositories list & sync query hooks

import { useGetQuery } from '../../api/api';
import { ENDPOINTS } from '../../api/endpoints';
import { useQueryClient } from '@tanstack/react-query';

const DEFAULT_OPTIONS = {
  staleTime: 30_000,
  refetchOnWindowFocus: false,
};

export function useReposList(params = undefined, options = {}) {
  return useGetQuery(ENDPOINTS.REPOSITORIES.LIST, params, { ...DEFAULT_OPTIONS, ...options });
}

// If your backend's sync endpoint returns the updated repositories list,
// use this hook to call the sync endpoint and read repos directly from its response.
export function useReposFromSync(options = {}) {
  return useGetQuery(ENDPOINTS.REPOSITORIES.SYNC, undefined, { enabled: true, ...options });
}

export function useSyncReposAndRefresh() {
  const qc = useQueryClient();
  const syncQuery = useSyncRepos({
    onSuccess: () => {
      // Ensure list cache is invalidated and immediately refetched so UI updates after sync
      qc.invalidateQueries({ queryKey: [ENDPOINTS.REPOSITORIES.LIST] });
      // trigger an immediate refetch of the repos list
      qc.refetchQueries({ queryKey: [ENDPOINTS.REPOSITORIES.LIST] });
    },
  });
  return syncQuery;
}