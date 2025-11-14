# Backend Integration Guide - SSE Message Buffering

## Problem Solved

**Issue**: For fast conversational responses (<300ms), the AI completes and sends the greeting **before** the SSE client can connect, causing the backend to miss the response.

**Solution**: Implemented **message buffering** that stores all events until the SSE client connects, ensuring no messages are lost even with late connections.

---

## How It Works

### Architecture

```
┌─────────────────┐
│  POST /refactor │ ──► Creates session, initializes buffer
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Background     │
│  Pipeline       │ ──► Sends messages to:
│  (Orchestrator) │     1. Queue (for live streaming)
└────────┬────────┘     2. Buffer (for late connections)
         │
         ▼
┌─────────────────────────────────────┐
│  GET /sse (connects LATE)          │
│                                     │
│  1. Drains buffer first (if any)   │ ──► All buffered events
│  2. Then streams from queue        │ ──► New events (if any)
└─────────────────────────────────────┘
```

### Message Flow

1. **POST `/api/refactor`**: 
   - Creates `session_id`
   - Initializes empty `session_buffers[session_id]` list
   - Starts background pipeline
   - Returns immediately with `session_id`

2. **Background Pipeline**:
   - Sends each event to **both**:
     - `session_queues[session_id]` (asyncio.Queue for live streaming)
     - `session_buffers[session_id]` (list for late connections)
   - Even completion signal (`None`) is buffered

3. **GET `/api/refactor/{session_id}/sse`**:
   - First, checks buffer: `session_buffers[session_id]`
   - If buffer has messages:
     - Yields all buffered messages as SSE events
     - Clears buffer
   - Then streams from queue for any remaining events

---

## Backend Integration (Java Spring Boot)

### RefactorService.java

```java
@Service
public class RefactorService {
    
    private final RestTemplate restTemplate;
    private final String pythonAiBaseUrl = "http://localhost:8000/api";
    
    /**
     * Start refactoring job and return session_id.
     * SSE connection can be delayed without losing messages!
     */
    public RefactorResponse startRefactor(RefactorRequest request) {
        String url = pythonAiBaseUrl + "/refactor";
        
        ResponseEntity<RefactorResponse> response = restTemplate.postForEntity(
            url, 
            request, 
            RefactorResponse.class
        );
        
        return response.getBody(); // Contains session_id
    }
    
    /**
     * Connect to SSE stream to receive events.
     * Can be called ANYTIME after startRefactor() - messages are buffered!
     * 
     * @param sessionId Session identifier from startRefactor()
     * @param eventListener Callback for each SSE event
     */
    public void streamProgress(
        String sessionId, 
        Consumer<ProgressUpdate> eventListener
    ) {
        String sseUrl = pythonAiBaseUrl + "/refactor/" + sessionId + "/sse";
        
        // Option 1: Using Spring WebFlux WebClient
        WebClient.create(sseUrl)
            .get()
            .accept(MediaType.TEXT_EVENT_STREAM)
            .retrieve()
            .bodyToFlux(String.class)
            .subscribe(event -> {
                // Parse SSE event
                if (event.startsWith("data: ")) {
                    String jsonData = event.substring(6);
                    ProgressUpdate update = parseJson(jsonData);
                    eventListener.accept(update);
                }
            });
    }
}
```

### ChatController.java

```java
@RestController
@RequestMapping("/api/chat")
public class ChatController {
    
    @Autowired
    private RefactorService refactorService;
    
    @PostMapping("/messages")
    public ResponseEntity<ChatResponse> sendMessage(@RequestBody ChatRequest request) {
        // 1. Forward to Python AI
        RefactorRequest aiRequest = convertToAiRequest(request);
        RefactorResponse aiResponse = refactorService.startRefactor(aiRequest);
        
        String sessionId = aiResponse.getSessionId();
        
        // 2. Save conversation to MySQL
        Conversation conversation = conversationRepository.save(
            new Conversation(request.getUserId(), request.getMessage(), sessionId)
        );
        
        // 3. Start SSE streaming in background (can be delayed!)
        CompletableFuture.runAsync(() -> {
            // Even if this runs AFTER greeting is sent, buffer will catch it!
            refactorService.streamProgress(sessionId, update -> {
                // Store updates in database
                saveProgressUpdate(conversation.getId(), update);
                
                // Optionally forward to WebSocket for frontend
                messagingTemplate.convertAndSend(
                    "/topic/chat/" + conversation.getId(),
                    update
                );
            });
        });
        
        // 4. Return response immediately
        return ResponseEntity.ok(new ChatResponse(
            conversation.getId(),
            sessionId,
            "Processing your request..."
        ));
    }
}
```

---

## Key Benefits for Backend Integration

### ✅ No Race Conditions

```java
// This WORKS even with delayed SSE connection:
RefactorResponse response = refactorService.startRefactor(request);
String sessionId = response.getSessionId();

// Save to database first (takes time)
conversationRepository.save(...);

// THEN connect to SSE - buffered messages still available!
refactorService.streamProgress(sessionId, eventListener);
```

### ✅ Flexible Architecture

Backend can choose when to connect:

1. **Immediate Connection** (normal case):
   ```java
   String sessionId = startRefactor(request);
   streamProgress(sessionId, listener);  // No buffering needed
   ```

2. **Delayed Connection** (after DB writes):
   ```java
   String sessionId = startRefactor(request);
   saveToDatabase(sessionId);           // Takes 100-500ms
   streamProgress(sessionId, listener);  // Buffer ensures no message loss
   ```

3. **On-Demand Connection** (for status checks):
   ```java
   // Connect anytime later to get buffered history
   streamProgress(sessionId, listener);  // Gets all buffered events
   ```

### ✅ Handles Fast Responses

For conversational greetings (<300ms):
- Without buffering: Backend might miss the greeting entirely
- With buffering: Greeting stored until backend connects

---

## Testing the Fix

### Test 1: Late SSE Connection (Conversational)

```bash
# 1. Start job
curl -X POST http://localhost:8000/api/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "demo_user",
    "user_prompt": "hello",
    "github_credentials": {...},
    "mode": "autonomous"
  }'

# Response: {"session_id": "session_20251113_180000_abc123", ...}

# 2. Wait 2 seconds (greeting already completed and buffered)
sleep 2

# 3. Connect to SSE (late) - should still get greeting!
curl -N http://localhost:8000/api/refactor/session_20251113_180000_abc123/sse
```

**Expected Output**:
```
data: {"message": "Hello! I'm RepoAI...", "status": "completed", ...}
```

### Test 2: Immediate Connection (Normal Case)

```bash
# 1. Start job
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/refactor \
  -H "Content-Type: application/json" \
  -d '{...}' | jq -r '.session_id')

# 2. Connect immediately (no buffer needed)
curl -N http://localhost:8000/api/refactor/$SESSION_ID/sse
```

**Both cases work identically** - messages delivered successfully.

---

## Automated Tests

Run the test suite to verify buffering:

```bash
cd /home/timmy/RepoAI/RepoAI_AI
uv run pytest tests/api/test_message_buffering.py -v
```

**Test Coverage**:
- ✅ `test_greeting_buffered_for_late_sse_connection` - Late connection gets buffered greeting
- ✅ `test_pipeline_events_buffered_for_late_connection` - Pipeline events buffered
- ✅ `test_immediate_sse_connection_no_buffer_needed` - Normal immediate connection works

All tests pass (3/3) ✅

---

## Performance Impact

### Memory Usage

- **Minimal**: Buffer stores only events for active sessions
- **Cleanup**: Buffers cleared after SSE client drains them
- **Typical size**: 1-5 events for conversational, 20-50 for refactoring

### Latency

- **No impact**: Events sent to both queue and buffer simultaneously
- **SSE connection**: Buffer drained first, then queue streaming continues
- **Backend delay tolerance**: Can delay SSE connection by seconds without message loss

---

## Production Considerations

### For Production Deployment

1. **Add TTL for buffers** (currently persist until SSE connects):
   ```python
   # Clean up old buffers after 5 minutes
   session_buffer_ttl = {}  # session_id -> timestamp
   
   async def cleanup_old_buffers():
       while True:
           now = time.time()
           for session_id, created_at in list(session_buffer_ttl.items()):
               if now - created_at > 300:  # 5 minutes
                   del session_buffers[session_id]
                   del session_buffer_ttl[session_id]
           await asyncio.sleep(60)
   ```

2. **Use Redis for distributed systems**:
   ```python
   # Store buffer in Redis for multiple Python AI instances
   redis_client.lpush(f"buffer:{session_id}", json.dumps(event))
   ```

3. **Add buffer size limits**:
   ```python
   MAX_BUFFER_SIZE = 100
   if len(session_buffers[session_id]) < MAX_BUFFER_SIZE:
       session_buffers[session_id].append(update)
   ```

---

## Summary

✅ **Problem Solved**: Late SSE connections no longer miss messages  
✅ **Backend Ready**: Java can safely delay SSE connection for DB writes  
✅ **Tested**: 3/3 automated tests pass  
✅ **Zero Breaking Changes**: Existing immediate connections work identically  
✅ **Performance**: Minimal overhead, no latency impact

**Ready for backend integration!** 🚀
