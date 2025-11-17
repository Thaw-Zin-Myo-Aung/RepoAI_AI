import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import SidebarLayout from "../components/slidebar";
import ChatMessages from "../components/ChatMessages";
import { useChatDetail } from "../libs/hooks/chat/queries";

function parseMetadataJson(str) {
  if (!str || typeof str !== "string") return null;
  try {
    return JSON.parse(str);
  } catch (_) {
    return null;
  }
}

export default function ChatHistoryDetail() {
  const { convoId } = useParams();

  const { data, isLoading, isError, error } = useChatDetail(convoId, {
    enabled: !!convoId,
  });

  const [chatMessages, setChatMessages] = useState([]);

  const chatRecords = useMemo(() => {
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.data)) return data.data;
    return data ? [data] : [];
  }, [data]);

  useEffect(() => {
    const msgs = [];
    (chatRecords || []).forEach((rec) => {
      if (rec?.content) {
        msgs.push({
          id: `user-${rec.id}`,
          sender: "user",
          message: rec.content,
        });
      }
      const meta = parseMetadataJson(rec?.metadataJson);
      const items = Array.isArray(meta?.ai_items) ? meta.ai_items : [];
      if (items.length > 0) {
        msgs.push({ id: `ai-${rec.id}`, sender: "robot", items });
      }
    });
    setChatMessages(msgs);
  }, [chatRecords]);

  // console.log("Chat Records:", chatRecords);

  return (
    <SidebarLayout>
      <div className="flex flex-col h-screen bg-[#0d0d0d] w-full text-white">
        <div className="flex-1 overflow-y-auto no-scrollbar w-full px-6 py-6 space-y-4">
          {isLoading && <div className="text-gray-400">Loading chat…</div>}
          {isError && (
            <div className="text-red-400">
              Error: {String(error?.message || error)}
            </div>
          )}

          {!isLoading && !isError && chatMessages.length === 0 && (
            <div className="text-gray-400">No messages to display.</div>
          )}

          {!isLoading &&
            !isError &&
            chatMessages.map((msg) => (
              <div key={msg.id} className="flex flex-col w-full">
                <ChatMessages chatMessages={[msg]} />
              </div>
            ))}
        </div>

        {/* No ChatInput here – read-only history view */}
      </div>
    </SidebarLayout>
  );
}
