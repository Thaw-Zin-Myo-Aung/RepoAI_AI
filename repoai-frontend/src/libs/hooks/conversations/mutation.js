// src/libs/hooks/conversations/mutation.js
// Conversation create / update / delete mutations using React Query

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../../api/api';
import { ENDPOINTS } from '../../api/endpoints';

const DEFAULT_OPTIONS = { retry: false };

/** Create a conversation (POST). Expects body as payload. */
export function useCreateConversation(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: (body) => api.post(ENDPOINTS.CONVERSATION.CREATE, body),
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      // invalidate conversations list so UI refreshes
      qc.invalidateQueries({ queryKey: [ENDPOINTS.CONVERSATION.LIST] });
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

/** Update a conversation. Call mutate with { id, body } */
export function useUpdateConversation(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ id, body } = {}) => {
      if (!id) throw new Error('id is required to update conversation');
      return api.put(ENDPOINTS.CONVERSATION.UPDATE(id), body);
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      // invalidate list and detail cache for the updated conversation
      qc.invalidateQueries({ queryKey: [ENDPOINTS.CONVERSATION.LIST] });
      qc.invalidateQueries({ queryKey: [ENDPOINTS.CONVERSATION.DETAIL(vars?.id)] });
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

/** Delete a conversation. Call mutate with { id } */
export function useDeleteConversation(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ id } = {}) => {
      if (!id) throw new Error('id is required to delete conversation');
      return api.delete(ENDPOINTS.CONVERSATION.DELETE(id));
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({ queryKey: [ENDPOINTS.CONVERSATION.LIST] });
      qc.invalidateQueries({ queryKey: [ENDPOINTS.CONVERSATION.DETAIL(vars?.id)] });
      if (typeof baseOnSuccess === 'function') baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

export default { useCreateConversation, useUpdateConversation, useDeleteConversation };
