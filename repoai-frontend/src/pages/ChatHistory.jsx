import React, { useState, useEffect } from "react";
import { Eye, Trash2, Pencil } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { useConversationsList } from "../libs/hooks/conversations/queries";
import {
  useDeleteConversation,
  useUpdateConversation,
} from "../libs/hooks/conversations/mutation";
import { useUser } from "../libs/stores/useUser";

const ChatHistory = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [pendingUpdateId, setPendingUpdateId] = useState(null);
  const { user } = useUser();
  const githubId =
    user?.githubId || user?.id || user?.github_id || user?.node_id || "";

  // Fetch conversations from the API
  const {
    data: conversations = [],
    isLoading,
    isError,
    error,
  } = useConversationsList();
  const { mutate: deleteConversation, isPending: isDeleting } =
    useDeleteConversation({
      onSettled: () => setPendingDeleteId(null),
      onSuccess: () => {
        // API returns 204; force full page refresh as requested
        navigate(0);
      },
    });
  const { mutate: updateConversation, isPending: isUpdating } =
    useUpdateConversation({
      onSettled: () => setPendingUpdateId(null),
      onSuccess: () => {
        // After successful update, refresh page to reflect changes
        navigate(0);
      },
    });
  console.log(conversations);
  // ✅ FIX: Added effect to detect state and clear sessions
  useEffect(() => {
    if (location.state?.clear) {
      // No-op: clearing from location will show empty list because conversations come from API
    }
  }, [location.state]);

  return (
    <div className="flex h-screen bg-[#121212] text-[#FFFFFF] p-6">
      <main className="flex-1 p-[5%]">
        <div className="max-w-6xl">
          <h2 className="text-4xl font-extrabold mb-2">Chat History</h2>
          <p className="text-[#FFFFFF]">
            You've completed{" "}
            <span className="font-semibold">{conversations.length}</span>{" "}
            refactoring sessions.
          </p>

          {/* ❌ Original Error: When table is empty, nothing was displayed → looked like white screen */}
          {/* ✅ FIX: Added empty state message */}
          {isLoading && (
            <div className="text-center text-gray-400 py-8">
              Loading chat history...
            </div>
          )}
          {isError && (
            <div className="text-center text-red-400 py-8">
              Error loading chat history: {String(error?.message || error)}
            </div>
          )}
          <div className="bg-[#212121] border border-[#404040] rounded-lg overflow-hidden mt-6">
            <div className="p-5 grid grid-cols-12 gap-4 bg-[#404040] rounded-t-lg font-semibold text-gray-300">
              <div className="col-span-5">Name</div>
              <div className="col-span-3">Date</div>
              <div className="col-span-4 flex justify-center">Action</div>
            </div>

            {!isLoading &&
              !isError &&
              (conversations.length === 0 ? (
                <div className="text-center text-gray-400 py-8">
                  No chat history available.
                </div>
              ) : (
                conversations.map((session, index) => (
                  <div
                    key={session.id}
                    className={`grid grid-cols-12 gap-4 p-5 cursor-pointer ${
                      index !== conversations.length - 1
                        ? "border-b border-gray-800"
                        : ""
                    }`}
                  >
                    <div className="col-span-5 text-white">{session.title}</div>
                    <div className="col-span-3 text-gray-400">
                      {session.updatedAt}
                    </div>
                    <div className="col-span-4 text-white font-semibold flex justify-center">
                      <button
                        className="mx-2 text-white font-semibold flex justify-center disabled:opacity-60 hover:text-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded"
                        title="View conversation"
                        aria-label="View conversation"
                        onClick={() => {
                          navigate(`/chat-history/${session.id}`);
                        }}
                      >
                        <Eye className="w-5 h-5" />
                      </button>
                      <button
                        type="button"
                        className="mx-2 text-white font-semibold flex justify-center disabled:opacity-60 hover:text-red-400 focus:outline-none focus:ring-2 focus:ring-red-500 rounded"
                        title={
                          isDeleting && pendingDeleteId === session.id
                            ? "Deleting conversation..."
                            : "Delete conversation"
                        }
                        aria-label={
                          isDeleting && pendingDeleteId === session.id
                            ? "Deleting conversation"
                            : "Delete conversation"
                        }
                        disabled={isDeleting && pendingDeleteId === session.id}
                        onClick={() => {
                          if (!githubId) {
                            alert(
                              "Missing GitHub user id; cannot authorize delete. Please re-login."
                            );
                            return;
                          }
                          if (confirm(`Delete conversation \"${session.title}\"?`)) {
                            setPendingDeleteId(session.id);
                            deleteConversation({ id: session.id, githubId });
                          }
                        }}
                      >
                        {isDeleting && pendingDeleteId === session.id ? (
                          <span className="text-xs tracking-wide animate-pulse">…</span>
                        ) : (
                          <Trash2 className="w-5 h-5" />
                        )}
                      </button>
                      <button
                        type="button"
                        className="mx-2 text-white font-semibold flex justify-center disabled:opacity-60 hover:text-green-400 focus:outline-none focus:ring-2 focus:ring-green-500 rounded"
                        title={
                          isUpdating && pendingUpdateId === session.id
                            ? "Renaming conversation..."
                            : "Rename conversation"
                        }
                        aria-label={
                          isUpdating && pendingUpdateId === session.id
                            ? "Renaming conversation"
                            : "Rename conversation"
                        }
                        disabled={isUpdating && pendingUpdateId === session.id}
                        onClick={() => {
                          const newTitle = prompt(
                            "Rename conversation",
                            session.title
                          );
                          if (
                            !newTitle ||
                            newTitle.trim() === "" ||
                            newTitle === session.title
                          )
                            return;
                          setPendingUpdateId(session.id);
                          updateConversation({
                            id: session.id,
                            body: { title: newTitle.trim() },
                          });
                        }}
                      >
                        {isUpdating && pendingUpdateId === session.id ? (
                          <span className="text-xs tracking-wide animate-pulse">…</span>
                        ) : (
                          <Pencil className="w-5 h-5" />
                        )}
                      </button>
                    </div>
                  </div>
                ))
              ))}
          </div>
        </div>
      </main>
    </div>
  );
};

export default ChatHistory;
