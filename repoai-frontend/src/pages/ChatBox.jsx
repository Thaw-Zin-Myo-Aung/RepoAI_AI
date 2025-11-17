import { useState, useEffect, useRef } from "react";
import SidebarLayout from "../components/slidebar";
import ChatMessages from "../components/ChatMessages";
import ChatInput from "../components/ChatInput";
import RefactorPreviewModal from "./Preview";
import { useParams } from "react-router-dom";
import { useCreateChat, useUpdateChat } from "../libs/hooks/chat/mutation";
import { useUser } from "../libs/stores/useUser";
import { useSession } from "../libs/stores/useSession";
import {
  useRefactorSSE,
  useRefactorSSEGet,
  useRepoHealthCheck,
} from "../libs/hooks/repoai/queries";
import { useAuthTokenQuery } from "../libs/hooks/auth/queries";
import { safeJSONStringify } from "../libs/utils/json";
import {
  useStartRefactor,
  useConfirmPlan,
  useConfirmValidation,
  useConfirmPush,
} from "../libs/hooks/repoai/mutation";
import { formatChatEvent } from "../libs/utils/formatChatEvent";

function ChatBox() {
  const [chatMessages, setChatMessages] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [activeRefactorMsgId, setActiveRefactorMsgId] = useState(null);
  const [refactorSessionId, setRefactorSessionId] = useState(null);
  const [pendingConfirmPlan, setPendingConfirmPlan] = useState(null); // { planId }
  const [pendingConfirmValidation, setPendingConfirmValidation] =
    useState(false);
  const [pendingConfirmPush, setPendingConfirmPush] = useState(false);
  const [isAiBusy, setIsAiBusy] = useState(false);
  const [currentAiBlockId, setCurrentAiBlockId] = useState(null);
  const currentAiBlockIdRef = useRef(null);
  const activeUserChatIdRef = useRef(null); // track latest user chatId for persistence
  const aiPersistItemsRef = useRef([]); // accumulate AI items to store in metadataJson
  const lastUserContentRef = useRef(""); // track the latest user's message content for persistence
  const chatEndRef = useRef(null); // ✅ ref for auto-scroll

  // Hardcoded example codes (later from backend)
  const originalCode = `data = request.get_json()
# Process the data
result = process_input(data['input'])
return jsonify({'status': 'success','result': result})`;

  const refactoredCode = `data = request.get_json()
if not data or 'input' not in data:
    raise BadRequest("Missing required 'input' field")
# Process the data
result = process_input(data['input'])
return jsonify({'status': 'success','result': result}), 200
except BadRequest as e:
    logger.warning(f"Bad request: {str(e)}")`;

  // 👋 Initial greeting
  useEffect(() => {
    setChatMessages([
      {
        message: "Hello! I'm your Repo AI assistant. How can I help you today?",
        sender: "robot",
        id: crypto.randomUUID(),
      },
    ]);
  }, []);

  // ✅ Auto-scroll to bottom whenever chatMessages change
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [chatMessages]);

  // 🧠 Handle user input
  const params = useParams();
  const createChat = useCreateChat();
  const updateChat = useUpdateChat();
  const user = useUser((s) => s.user);
  const session = useSession((s) => s.currentConversation);
  const currentRepo = useSession((s) => s.currentRepo);
  const currentBranch = useSession((s) => s.currentBranch);
  const authToken = useSession((s) => s.authToken);
  const setAuthToken = useSession((s) => s.setAuthToken);
  // repoai health check (disabled by default; we will trigger manually)
  const { refetch: refetchRepoaiHealth } = useRepoHealthCheck({
    enabled: false,
  });
  const { refetch: refetchAuthToken } = useAuthTokenQuery(undefined, {
    enabled: false,
  });
  const startRefactor = useStartRefactor();
  const confirmPlan = useConfirmPlan();
  const confirmValidation = useConfirmValidation();
  const confirmPush = useConfirmPush();
  const sseErrorShownRef = useRef(false);
  // const refactorSSE = useRefactorSSEGet(refactorSessionId, { enabled: !!refactorSessionId });
  const refactorSSEStream = useRefactorSSE(refactorSessionId, {
    enabled: !!refactorSessionId,
    // Show only messages coming from backend; never auto-close on terminal/named events
    isTerminalEvent: () => false,
    eventTypes: [],
    onMessage: (evt) => {
      const formatted = formatChatEvent(evt);
      const meta = formatted?.meta;

      // If this event requests a confirmation, close the current aggregation block BEFORE aggregating
      if (meta?.requires_confirmation) {
        // Set pending confirmation type
        if (meta?.confirmation_type === "validation") {
          setPendingConfirmValidation(true);
        } else if (meta?.confirmation_type === "push") {
          setPendingConfirmPush(true);
        } else {
          const planId = meta?.data?.plan_id || null;
          setPendingConfirmPlan({ planId });
        }
        // Exit busy and reset the current block immediately so next AI phase starts fresh
        setIsAiBusy(false);
        currentAiBlockIdRef.current = null;
        setCurrentAiBlockId(null);
        // Show the confirmation prompt as a plain message (not part of aggregated block)
        setChatMessages((prev) => [
          ...prev,
          {
            message: formatted.text,
            sender: "robot",
            kind: formatted.kind,
            meta: formatted.meta,
            id: crypto.randomUUID(),
          },
        ]);
        return; // do not aggregate this event
      }

      // Helper to build an aggregated item
      const buildItem = () => {
        if (meta?.data?.raw_line)
          return { type: "raw_line", raw: meta.data.raw_line };
        if (meta?.data?.plan_summary) return { type: "plan_summary", meta };
        if (meta?.data?.validation_summary)
          return { type: "validation_summary", meta };
        if (meta?.data?.push_summary) return { type: "push_summary", meta };
        if (
          meta?.data?.original_content != null ||
          meta?.data?.modified_content != null ||
          meta?.data?.diff != null
        ) {
          return {
            type: "file_change",
            meta,
            fileChange: {
              filePath: meta?.data?.file_path,
              operation: meta?.data?.operation,
              original: meta?.data?.original_content ?? null,
              modified: meta?.data?.modified_content ?? null,
            },
          };
        }
        return {
          type: "text",
          text: formatted.text,
          kind: formatted.kind,
          meta,
        };
      };

      // Build once so we can both render and persist
      const newItem = buildItem();

      // If AI is busy, aggregate messages into a single block
      setChatMessages((prev) => {
        const next = [...prev];
        let blockId = currentAiBlockIdRef.current;
        let idx = -1;

        if (!blockId) {
          // Create a new aggregation block and set index to the newly pushed item
          blockId = crypto.randomUUID();
          currentAiBlockIdRef.current = blockId;
          setCurrentAiBlockId(blockId);
          next.push({ id: blockId, sender: "robot", items: [] });
          idx = next.length - 1;
        } else {
          // Try to find existing block index; if not found, (re)create it
          idx = next.findIndex((m) => m.id === blockId);
          if (idx === -1) {
            next.push({ id: blockId, sender: "robot", items: [] });
            idx = next.length - 1;
          }
        }

        const msg = next[idx];
        const items = Array.isArray(msg.items)
          ? [...msg.items, newItem]
          : [newItem];
        next[idx] = { ...msg, items };
        return next;
      });

      // Persist AI response incrementally to the last user chat record
      try {
        const convIdPersist =
          params?.convId || params?.conversationId || params?.id || session?.id;
        console.log(
          "Persisting AI metadata to conv:",
          convIdPersist,
          activeUserChatIdRef.current
        );
        const chatIdForUpdate = activeUserChatIdRef.current;
        if (convIdPersist && chatIdForUpdate) {
          aiPersistItemsRef.current = [...aiPersistItemsRef.current, newItem];
          const metadataJsonObj = { ai_items: aiPersistItemsRef.current };
          const metadataJson = safeJSONStringify(metadataJsonObj);
              const githubIdVal = Number(user?.githubId) || 0;
              updateChat.mutate({
                conv_id: convIdPersist,
                chatId: chatIdForUpdate,
                body: {
                  metadataJson,
                  content: lastUserContentRef.current,
                  ...(githubIdVal > 0 ? { githubId: githubIdVal } : {}),
                },
              });
        }
      } catch (e) {
        // Non-fatal persistence error; continue UI flow
        console.warn("AI metadata update failed", e);
      }
    },
    // Suppress connection lifecycle messages in chat
    onOpen: () => {
      sseErrorShownRef.current = false;
    },
    onError: () => {
      setIsAiBusy(false);
      currentAiBlockIdRef.current = null;
      setCurrentAiBlockId(null);
    },
    onClose: () => {},
    // No retries; just consume whatever the backend sends
    retry: { enabled: false },
    // No idle timeout so stream won't close from client side
    idleTimeoutMs: undefined,
  });

  console.log(chatMessages);

  const handleUserInput = async (text) => {
    // Remember the latest user content so we can include it in subsequent update payloads
    lastUserContentRef.current = text;
    const userMsg = { message: text, sender: "user", id: crypto.randomUUID() };
    setChatMessages((prev) => [...prev, userMsg]);

    // Determine conversation id: prefer route param convId, fallback to session
    const convId =
      params?.convId || params?.conversationId || params?.id || session?.id;

    // Build chat payload: convoId (conv_id), optional client chatId (we'll override with server id), gid, content, metadataJson
    // We'll still generate a temporary client id but WILL NOT persist with it; server-issued id is authoritative.
    const clientTempChatId = crypto.randomUUID();
    const gid = Number(user?.githubId || user?.id) || 0;
    const payload = {
      conv_id: convId,
      body: {
        chatId: clientTempChatId,
        gid,
        content: text,
        metadataJson: null,
      },
    };

    // Do NOT pre-bind to clientTempChatId for updates to avoid 404 on server; wait for server response.
    aiPersistItemsRef.current = [];

    try {
      // fire-and-forget; you can await createChat.mutateAsync if you want to block
      const createRes = await createChat.mutateAsync(payload);
      // Extract server-issued chat id from various possible response shapes
      const serverChatId =
        createRes?.chatId ||
        createRes?.id ||
        createRes?.data?.chatId ||
        createRes?.data?.id ||
        createRes?.data?.chat?.id ||
        createRes?.data?.chatId ||
        null;
        console.log("Create chat response", createRes, "extracted chatId:", serverChatId);
      if (serverChatId != null) {
        activeUserChatIdRef.current = String(serverChatId);
        console.log("[ChatBox] Bound server chatId for persistence:", serverChatId);
      } else {
        console.warn(
          "[ChatBox] Server chatId not found in create response; updates will be skipped until available.",
          createRes
        );
      }
    } catch (err) {
      console.error("Create chat message failed", err);
    }

    // If a VALIDATION confirmation is pending, send this text instead of starting a new refactor
    if (pendingConfirmValidation && refactorSessionId) {
      setIsAiBusy(true);
      // New busy phase after user confirms: start a fresh aggregation block
      currentAiBlockIdRef.current = null;
      setCurrentAiBlockId(null);
      try {
        await confirmValidation.mutateAsync({
          session_id: refactorSessionId,
          body: { session_id: refactorSessionId, user_response: text },
        });
      } catch (err) {
        console.error("Confirm validation failed", err);
      } finally {
        setPendingConfirmValidation(false);
        // keep busy until next server response changes state
      }
      return; // do not proceed
    }

    // If a PUSH confirmation is pending, send this text instead of starting a new refactor
    if (pendingConfirmPush && refactorSessionId) {
      setIsAiBusy(true);
      // New busy phase after user confirms: start a fresh aggregation block
      currentAiBlockIdRef.current = null;
      setCurrentAiBlockId(null);
      try {
        await confirmPush.mutateAsync({
          session_id: refactorSessionId,
          body: { session_id: refactorSessionId, user_response: text },
        });
      } catch (err) {
        console.error("Confirm push failed", err);
      } finally {
        setPendingConfirmPush(false);
        // keep busy until next server response changes state
      }
      return; // do not proceed
    }

    // If a PLAN confirmation is pending, send this text instead of starting a new refactor
    if (pendingConfirmPlan && refactorSessionId) {
      setIsAiBusy(true);
      // New busy phase after user confirms: start a fresh aggregation block
      currentAiBlockIdRef.current = null;
      setCurrentAiBlockId(null);
      try {
        await confirmPlan.mutateAsync({
          session_id: refactorSessionId,
          body: { session_id: refactorSessionId, user_response: text },
        });
      } catch (err) {
        console.error("Confirm plan failed", err);
      } finally {
        setPendingConfirmPlan(null);
        // keep busy until next server response changes state
      }
      return; // do not proceed to token/health/startRefactor
    }
    // First: call token API (query refetch) and persist to session store, then health check
    let fetchedToken = null;
    try {
      const { data: tokenData } = await refetchAuthToken();
      if (tokenData != null) {
        const token =
          tokenData?.accessToken ||
          tokenData?.token ||
          tokenData?.access_token ||
          (typeof tokenData === "string" ? tokenData : null);
        fetchedToken = token || null;
        if (fetchedToken) {
          try {
            setAuthToken(fetchedToken);
          } catch (_) {}
        } else {
          console.warn("Token endpoint returned empty payload", tokenData);
        }
      }
    } catch (tokErr) {
      console.error("Token generation failed", tokErr);
    }

    // After token, trigger a RepoAI health check
    try {
      await refetchRepoaiHealth();
    } catch (hcErr) {
      console.error("RepoAI health check failed", hcErr);
    }
    // Build start-refactor payload and call RepoAI
    try {
      const repository_url = currentRepo?.html_url;
      const branchName = currentBranch?.name;
      const userId = String(user?.githubId);
      // Prefer freshly fetched token, then store's latest, then the captured authToken from hook
      const accessToken =
        fetchedToken ||
        (useSession.getState && useSession.getState().authToken) ||
        authToken;

      const startPayload = {
        user_id: userId,
        user_prompt: text,
        github_credentials: {
          access_token: accessToken,
          repository_url,
          branch: branchName,
        },
        mode: "interactive-detailed",
      };

      setIsAiBusy(true);
      // Start of a new busy period; reset current aggregation block
      currentAiBlockIdRef.current = null;
      setCurrentAiBlockId(null);
      const startRes = await startRefactor.mutateAsync(startPayload);
      // extract session id from response
      console.log("Start refactor response", startRes);
      const sid = startRes?.data?.session_id;
      if (sid) {
        setRefactorSessionId(sid);
        console.log("Refactor session started:", sid);
      } else {
        console.warn("Start refactor response missing session id", startRes);
      }
    } catch (startErr) {
      console.error("Start refactor failed", startErr);
    }
  };

  // 🧩 Handle “Show Preview” button click
  const handleShowPreview = (msgId) => {
    setActiveRefactorMsgId(msgId);
    setShowModal(true);
  };

  // 💾 Handle “Accept and Save”
  const handleAcceptAndSave = () => {
    const userMsg = {
      message: "Accept and Save",
      sender: "user",
      id: crypto.randomUUID(),
    };
    console.log("Refactored code logged:", refactoredCode);
    setShowModal(false);
  };

  // ❌ Handle “Cancel”
  const handleCancel = () => {
    const userMsg = {
      message: "Cancel",
      sender: "user",
      id: crypto.randomUUID(),
    };
    console.log("Original code logged:", originalCode);
    setShowModal(false);
  };

  return (
    <SidebarLayout>
      <div className="flex flex-col h-screen bg-[#0d0d0d] w-full text-white">
        {/* Scrollable chat area */}
        <div className="flex-1 overflow-y-auto no-scrollbar w-full px-6 py-6 space-y-4">
          {chatMessages.map((msg) => (
            <div key={msg.id} className="flex flex-col">
              <ChatMessages chatMessages={[msg]} />

              {/* Inline preview button only for AI refactor messages */}
              {msg.sender === "robot" && msg.action === "showPreview" && (
                <div className="flex justify-start mt-2 ml-12">
                  <button
                    onClick={() => handleShowPreview(msg.id)}
                    className="bg-[#FFFFFF] text-black font-semibold px-5 py-2 rounded-lg hover:bg-[#ffb733] transition-all duration-200"
                  >
                    Show Refactor Preview
                  </button>
                </div>
              )}
            </div>
          ))}

          {/* ✅ Invisible scroll target for auto-scroll */}
          <div ref={chatEndRef} />
        </div>

        {/* Input at bottom */}
        <div className="sticky bottom-0 w-full">
          <ChatInput
            chatMessages={chatMessages}
            setChatMessages={setChatMessages}
            onSend={handleUserInput}
            placeholder={
              pendingConfirmValidation
                ? "Type your validation choice…"
                : pendingConfirmPush
                ? "Type your push confirmation…"
                : pendingConfirmPlan
                ? "Type your confirmation message…"
                : "Enter your prompt"
            }
            disabled={isAiBusy}
            loading={isAiBusy}
          />
        </div>

        {/* Popup Modal */}
        {showModal && (
          <RefactorPreviewModal
            originalCode={originalCode}
            refactoredCode={refactoredCode}
            onAccept={handleAcceptAndSave}
            onCancel={handleCancel}
          />
        )}
      </div>
    </SidebarLayout>
  );
}

export default ChatBox;
