// src/libs/hooks/chat/mutation.js
// Chat create / update / delete mutations (chat messages under a conversation)

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/api";
import { ENDPOINTS } from "../../api/endpoints";

const DEFAULT_OPTIONS = { retry: false };

/** Create a chat message under a conversation. Call mutate with { conv_id, body } */
export function useCreateChat(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ conv_id, body } = {}) => {
      if (!conv_id) throw new Error("conv_id is required to create chat");
      return api.post(ENDPOINTS.CHAT.CREATE(conv_id), body);
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      // invalidate messages list and conversation detail so UI refreshes
      return data;
    },
    ...options,
  });
}

/** Update a chat message. Call mutate with { conv_id, chatId, body } */
export function useUpdateChat(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ conv_id, chatId, body } = {}) => {
      if (!conv_id) throw new Error("conv_id is required to update chat");
      if (!chatId) throw new Error("chatId is required to update chat");
      return api.put(ENDPOINTS.CHAT.UPDATE(conv_id, chatId), { ...body });
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({
        queryKey: [ENDPOINTS.CONVERSATION.MESSAGES(vars?.conv_id)],
      });
      qc.invalidateQueries({
        queryKey: [ENDPOINTS.CONVERSATION.DETAIL(vars?.conv_id)],
      });
      if (typeof baseOnSuccess === "function") baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

/** Delete a chat message. Call mutate with { conv_id, chatId } */
export function useDeleteChat(options = {}) {
  const qc = useQueryClient();
  const baseOnSuccess = options.onSuccess;
  return useMutation({
    mutationFn: ({ conv_id, chatId } = {}) => {
      if (!conv_id) throw new Error("conv_id is required to delete chat");
      if (!chatId) throw new Error("chatId is required to delete chat");
      // delete endpoint for chat currently uses conv_id; pass chatId in body or query as backend expects
      return api.delete(
        ENDPOINTS.CHAT.DELETE(conv_id) + `?chatId=${encodeURIComponent(chatId)}`
      );
    },
    ...DEFAULT_OPTIONS,
    onSuccess: (data, vars, ctx) => {
      qc.invalidateQueries({
        queryKey: [ENDPOINTS.CONVERSATION.MESSAGES(vars?.conv_id)],
      });
      qc.invalidateQueries({
        queryKey: [ENDPOINTS.CONVERSATION.DETAIL(vars?.conv_id)],
      });
      if (typeof baseOnSuccess === "function") baseOnSuccess(data, vars, ctx);
    },
    ...options,
  });
}

export default { useCreateChat, useUpdateChat, useDeleteChat };
