// src/libs/hooks/repoai/mutation.js
// RepoAI mutations using the `repoai` client

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { repoai } from '../../api/repoai';

const DEFAULT_OPTIONS = { retry: false };

/**
 * Start a refactor job on the RepoAI service.
 * Call with the request body the backend expects, e.g. { repoId, branchId, files, options }
 * Usage: const start = useStartRefactor(); start.mutate(payload)
 */
export function useStartRefactor(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: (body) => {
      return repoai.post('api/refactor', body);
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      // Invalidate RepoAI health so UI can refresh status if desired
      try {
        qc.invalidateQueries({ queryKey: ['api/health'] });
      } catch (_) {}
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

export default { useStartRefactor };

/** Confirm plan for a refactor session (POST)
 * Call with { session_id, body }
 */
export function useConfirmPlan(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ session_id, body } = {}) => {
      if (!session_id) throw new Error('session_id is required to confirm plan');
      return repoai.post(`api/refactor/${session_id}/confirm-plan`, body);
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      try { qc.invalidateQueries({ queryKey: ['api/health'] }); } catch (_) {}
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

/** Confirm validation for a refactor session (POST)
 * Call with { session_id, body }
 */
export function useConfirmValidation(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ session_id, body } = {}) => {
      if (!session_id) throw new Error('session_id is required to confirm validation');
      return repoai.post(`api/refactor/${session_id}/confirm-validation`, body);
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      try { qc.invalidateQueries({ queryKey: ['api/health'] }); } catch (_) {}
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

/** Confirm push for a refactor session (POST)
 * Call with { session_id, body }
 */
export function useConfirmPush(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ session_id, body } = {}) => {
      if (!session_id) throw new Error('session_id is required to confirm push');
      return repoai.post(`api/refactor/${session_id}/confirm-push`, body);
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      try { qc.invalidateQueries({ queryKey: ['api/health'] }); } catch (_) {}
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}
