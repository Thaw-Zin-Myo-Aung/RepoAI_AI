import { useRef, useEffect } from "react";
import { ChatMessage } from "./ChatMessage";

function ChatMessages({ chatMessages }) {
  const chatMessagesRef = useRef(null);

  useEffect(() => {
    const containerElem = chatMessagesRef.current;
    if (containerElem) {
      containerElem.scrollTop = containerElem.scrollHeight;
    }
  }, [chatMessages]);

  return (
    <div
      ref={chatMessagesRef}
      className="flex flex-col overflow-y-auto bg-[#0d0d0d] w-[100%]"
    >
      {chatMessages.length === 0 ? (
        <p className="text-gray-500 text-center mt-48">
          Start your conversation 💬
        </p>
      ) : (
        chatMessages.map((chatMessage) => (
          <ChatMessage
            key={chatMessage.id}
            message={chatMessage.message}
            sender={chatMessage.sender}
            kind={chatMessage.kind}
            meta={chatMessage.meta}
            items={chatMessage.items}
          />
        ))
      )}
    </div>
  );
}

export default ChatMessages;
