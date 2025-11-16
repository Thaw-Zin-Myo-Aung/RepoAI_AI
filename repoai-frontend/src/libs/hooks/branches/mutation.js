// src/libs/hooks/branches/mutation.js
// Branches sync mutations (POST) using React Query's useMutation.

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/api';
import { ENDPOINTS } from '../../api/endpoints';

const DEFAULT_OPTIONS = {
  retry: false,
};

/**
 * POST / sync branches for an owner/repo. Use when the backend expects a POST
 * to trigger a sync process (and optionally returns the branches payload).
 *
 * Usage: const mutation = useSyncBranchesMutation(owner, repo);
 * mutation.mutate();
 */
export function useSyncBranchesMutation(options = {}) {
  // mutation expects variables: { owner, repo, body }
  return useMutation({
    mutationFn: ({ owner, repo, body } = {}) => {
      if (!owner || !repo) throw new Error('owner and repo are required for sync');
      const endpoint = ENDPOINTS.BRANCHES.SYNC_BRANCHES(owner, repo);
      return api.post(endpoint, body);
    },
    ...DEFAULT_OPTIONS,
    ...options,
  });
}

/**
 * Call sync mutation and then invalidate + refetch branches list cache so UI
 * reflects the new branches. Provide repoId to target the correct cache key.
 *
 * Usage: const sync = useSyncBranchesAndRefreshMutation(owner, repo, repoId);
 * sync.mutate();
 */
export function useSyncBranchesAndRefreshMutation(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useSyncBranchesMutation({
    onSuccess: (data, vars, ctx) => {
      // vars is the variables object passed to mutate / mutateAsync
      const repoId = vars?.repoId;
      if (repoId) {
        qc.invalidateQueries({ queryKey: [ENDPOINTS.BRANCHES.LIST(repoId)] });
        qc.refetchQueries({ queryKey: [ENDPOINTS.BRANCHES.LIST(repoId)] });
      }
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

export default {
  useSyncBranchesMutation,
  useSyncBranchesAndRefreshMutation,
};
