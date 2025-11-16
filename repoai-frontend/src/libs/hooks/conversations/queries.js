// src/libs/hooks/conversations/queries.js
// Conversations GET hooks (list, detail, messages) using useGetQuery

import { useGetQuery } from '../../api/api';
import { ENDPOINTS } from '../../api/endpoints';

const DEFAULT_OPTIONS = {
  staleTime: 20_000,
  refetchOnWindowFocus: false,
};

/**
 * Fetch paginated/list of conversations.
 * params can contain pagination/filters (e.g. { page, per_page }).
 */
export function useConversationsList(convIdOrParams = undefined, params = undefined, options = {}) {
  // If first arg is a string/number, treat it as a conv_id and call LIST(conv_id)
  if (convIdOrParams && (typeof convIdOrParams === 'string' || typeof convIdOrParams === 'number')) {
    const convId = convIdOrParams;
    const endpoint = typeof ENDPOINTS.CONVERSATION.LIST === 'function' ? ENDPOINTS.CONVERSATION.LIST(convId) : ENDPOINTS.CONVERSATION.LIST;
    return useGetQuery(endpoint, params, { ...DEFAULT_OPTIONS, ...options });
  }

  // Otherwise treat first arg as params
  // Ensure we pass a string endpoint to the API helper. If the registry exported LIST as
  // a function (possibly `() => 'api/conversations'`) call it with no args to get the string.
  const endpoint = typeof ENDPOINTS.CONVERSATION.LIST === 'function'
    ? ENDPOINTS.CONVERSATION.LIST()
    : ENDPOINTS.CONVERSATION.LIST;
  const queryParams = convIdOrParams;
  return useGetQuery(endpoint, queryParams, { ...DEFAULT_OPTIONS, ...options });
}

/**
 * Fetch conversation detail by id.
 * Usage: useConversationDetail(conversationId)
 */
export function useConversationDetail(conversationId, options = {}) {
  if (!conversationId) return useGetQuery('__conversation_detail_not_set__', undefined, { enabled: false, ...options });
  return useGetQuery(ENDPOINTS.CONVERSATION.DETAIL(conversationId), undefined, { ...DEFAULT_OPTIONS, ...options });
}

/**
 * Fetch messages for a conversation id.
 * Usage: useConversationMessages(conversationId, { enabled: !!conversationId })
 */
export function useConversationMessages(conversationId, params = undefined, options = {}) {
  if (!conversationId) return useGetQuery('__conversation_messages_not_set__', undefined, { enabled: false, ...options });
  return useGetQuery(ENDPOINTS.CONVERSATION.MESSAGES(conversationId), params, { ...DEFAULT_OPTIONS, ...options });
}

export default {
  useConversationsList,
  useConversationDetail,
  useConversationMessages,
};
