// src/libs/hooks/chat/queries.js
// Chat GET hooks: fetch single chat message detail

import { useGetQuery } from "../../api/api";
import { ENDPOINTS } from "../../api/endpoints";

const DEFAULT_OPTIONS = {
  staleTime: 20_000,
  refetchOnWindowFocus: false,
};

/**
 * Fetch a single chat detail by conversation id and chat id.
 * Usage: useChatDetail(convoId, chatId, { enabled: !!convoId && !!chatId })
 */
export function useChatDetail(conversationId, options = {}) {
  if (!conversationId) {
    return useGetQuery(
      ENDPOINTS.CONVERSATION.DETAIL(conversationId),
      undefined,
      {
        enabled: false,
        ...options,
      }
    );
  }
  // Using the same endpoint path as update (GET should be supported server-side)
  const endpoint = ENDPOINTS.CONVERSATION.DETAIL(conversationId);
  return useGetQuery(endpoint, undefined, { ...DEFAULT_OPTIONS, ...options });
}

export default { useChatDetail };
