# Phase 2 Java Backend Integration Guide

## Overview
This guide helps integrate Phase 2 interactive confirmations with the Java Spring Boot backend.

**Time Estimate:** 4-6 hours  
**Difficulty:** Medium  
**Prerequisites:** Python API running on localhost:8000

---

## Step 1: Update RefactorRequest Model (30 min)

### 1.1 Create ExecutionMode Enum

**File:** `src/main/java/th/ac/kmitl/model/ExecutionMode.java`

```java
package th.ac.kmitl.model;

import com.fasterxml.jackson.annotation.JsonValue;

public enum ExecutionMode {
    AUTONOMOUS("autonomous"),
    INTERACTIVE("interactive"),
    INTERACTIVE_DETAILED("interactive-detailed");

    private final String value;

    ExecutionMode(String value) {
        this.value = value;
    }

    @JsonValue
    public String getValue() {
        return value;
    }
}
```

### 1.2 Update RefactorRequest

**File:** `src/main/java/th/ac/kmitl/model/RefactorRequest.java`

```java
package th.ac.kmitl.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class RefactorRequest {
    @JsonProperty("user_id")
    private String userId;
    
    @JsonProperty("user_prompt")
    private String userPrompt;
    
    @JsonProperty("github_credentials")
    private GitHubCredentials githubCredentials;
    
    // NEW: Add execution mode (defaults to interactive)
    @JsonProperty("mode")
    private ExecutionMode mode = ExecutionMode.INTERACTIVE;
}
```

---

## Step 2: Create Confirmation Models (30 min)

### 2.1 PlanConfirmationRequest

**File:** `src/main/java/th/ac/kmitl/model/PlanConfirmationRequest.java`

```java
package th.ac.kmitl.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class PlanConfirmationRequest {
    // Option 1: Structured format
    @JsonProperty("action")
    private String action;  // "approve", "cancel", "modify"
    
    // Option 2: Natural language format
    @JsonProperty("user_response")
    private String userResponse;  // "yes but use Redis instead"
    
    // Optional: For modify action
    @JsonProperty("modifications")
    private String modifications;
    
    // Factory methods for convenience
    public static PlanConfirmationRequest approve() {
        PlanConfirmationRequest req = new PlanConfirmationRequest();
        req.setAction("approve");
        return req;
    }
    
    public static PlanConfirmationRequest cancel() {
        PlanConfirmationRequest req = new PlanConfirmationRequest();
        req.setAction("cancel");
        return req;
    }
    
    public static PlanConfirmationRequest modify(String modifications) {
        PlanConfirmationRequest req = new PlanConfirmationRequest();
        req.setAction("modify");
        req.setModifications(modifications);
        return req;
    }
    
    public static PlanConfirmationRequest naturalLanguage(String userResponse) {
        PlanConfirmationRequest req = new PlanConfirmationRequest();
        req.setUserResponse(userResponse);
        return req;
    }
}
```

### 2.2 PushConfirmationRequest

**File:** `src/main/java/th/ac/kmitl/model/PushConfirmationRequest.java`

```java
package th.ac.kmitl.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class PushConfirmationRequest {
    @JsonProperty("action")
    private String action;  // "approve", "cancel"
    
    // Optional overrides
    @JsonProperty("branch_name")
    private String branchName;
    
    @JsonProperty("commit_message")
    private String commitMessage;
    
    // Factory methods
    public static PushConfirmationRequest approve() {
        PushConfirmationRequest req = new PushConfirmationRequest();
        req.setAction("approve");
        return req;
    }
    
    public static PushConfirmationRequest cancel() {
        PushConfirmationRequest req = new PushConfirmationRequest();
        req.setAction("cancel");
        return req;
    }
}
```

### 2.3 ConfirmationResponse

**File:** `src/main/java/th/ac/kmitl/model/ConfirmationResponse.java`

```java
package th.ac.kmitl.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.Data;

@Data
public class ConfirmationResponse {
    @JsonProperty("status")
    private String status;  // "resumed", "cancelled", "waiting"
    
    @JsonProperty("message")
    private String message;
}
```

---

## Step 3: Create ConfirmationController (1 hour)

**File:** `src/main/java/th/ac/kmitl/controller/ConfirmationController.java`

```java
package th.ac.kmitl.controller;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import th.ac.kmitl.model.ConfirmationResponse;
import th.ac.kmitl.model.PlanConfirmationRequest;
import th.ac.kmitl.model.PushConfirmationRequest;
import th.ac.kmitl.service.PythonApiClient;

@Slf4j
@RestController
@RequestMapping("/api/sessions")
@RequiredArgsConstructor
public class ConfirmationController {

    private final PythonApiClient pythonApiClient;

    @PostMapping("/{sessionId}/confirm/plan")
    public ResponseEntity<ConfirmationResponse> confirmPlan(
            @PathVariable String sessionId,
            @RequestBody PlanConfirmationRequest request) {
        
        log.info("Confirming plan for session: {}, action: {}, userResponse: {}", 
                 sessionId, request.getAction(), request.getUserResponse());
        
        try {
            ConfirmationResponse response = pythonApiClient.confirmPlan(sessionId, request);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("Failed to confirm plan for session: {}", sessionId, e);
            return ResponseEntity.status(500).body(createErrorResponse(e.getMessage()));
        }
    }

    @PostMapping("/{sessionId}/confirm/push")
    public ResponseEntity<ConfirmationResponse> confirmPush(
            @PathVariable String sessionId,
            @RequestBody PushConfirmationRequest request) {
        
        log.info("Confirming push for session: {}, action: {}", sessionId, request.getAction());
        
        try {
            ConfirmationResponse response = pythonApiClient.confirmPush(sessionId, request);
            return ResponseEntity.ok(response);
        } catch (Exception e) {
            log.error("Failed to confirm push for session: {}", sessionId, e);
            return ResponseEntity.status(500).body(createErrorResponse(e.getMessage()));
        }
    }

    @GetMapping("/{sessionId}")
    public ResponseEntity<?> getSessionStatus(@PathVariable String sessionId) {
        log.info("Getting status for session: {}", sessionId);
        
        try {
            // Forward to Python API
            return pythonApiClient.getSessionStatus(sessionId);
        } catch (Exception e) {
            log.error("Failed to get session status: {}", sessionId, e);
            return ResponseEntity.status(500).body(createErrorResponse(e.getMessage()));
        }
    }

    private ConfirmationResponse createErrorResponse(String message) {
        ConfirmationResponse response = new ConfirmationResponse();
        response.setStatus("error");
        response.setMessage(message);
        return response;
    }
}
```

---

## Step 4: Update PythonApiClient (1-2 hours)

**File:** `src/main/java/th/ac/kmitl/service/PythonApiClient.java`

```java
package th.ac.kmitl.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import th.ac.kmitl.model.*;

@Slf4j
@Service
public class PythonApiClient {

    @Value("${python.api.url:http://localhost:8000}")
    private String pythonApiUrl;

    private final RestTemplate restTemplate;

    public PythonApiClient(RestTemplate restTemplate) {
        this.restTemplate = restTemplate;
    }

    /**
     * Submit refactor request to Python API
     */
    public String submitRefactor(RefactorRequest request) {
        String url = pythonApiUrl + "/api/refactor";
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<RefactorRequest> entity = new HttpEntity<>(request, headers);
        
        log.info("Submitting refactor to Python API: {}", url);
        ResponseEntity<String> response = restTemplate.postForEntity(url, entity, String.class);
        
        // Extract session_id from response
        // Response format: {"session_id": "abc123", "message": "..."}
        String sessionId = extractSessionId(response.getBody());
        log.info("Refactor submitted, session_id: {}", sessionId);
        
        return sessionId;
    }

    /**
     * Confirm plan with approval/cancellation/modification
     */
    public ConfirmationResponse confirmPlan(String sessionId, PlanConfirmationRequest request) {
        String url = pythonApiUrl + "/api/sessions/" + sessionId + "/confirm/plan";
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<PlanConfirmationRequest> entity = new HttpEntity<>(request, headers);
        
        log.info("Confirming plan for session {}: action={}, userResponse={}", 
                 sessionId, request.getAction(), request.getUserResponse());
        
        return restTemplate.postForObject(url, entity, ConfirmationResponse.class);
    }

    /**
     * Confirm push with approval/cancellation
     */
    public ConfirmationResponse confirmPush(String sessionId, PushConfirmationRequest request) {
        String url = pythonApiUrl + "/api/sessions/" + sessionId + "/confirm/push";
        
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        HttpEntity<PushConfirmationRequest> entity = new HttpEntity<>(request, headers);
        
        log.info("Confirming push for session {}: action={}", sessionId, request.getAction());
        
        return restTemplate.postForObject(url, entity, ConfirmationResponse.class);
    }

    /**
     * Get session status
     */
    public ResponseEntity<?> getSessionStatus(String sessionId) {
        String url = pythonApiUrl + "/api/sessions/" + sessionId;
        log.info("Getting session status: {}", url);
        
        return restTemplate.getForEntity(url, Object.class);
    }

    private String extractSessionId(String responseBody) {
        // Simple JSON parsing (use Jackson in production)
        // Response: {"session_id": "abc123", ...}
        int start = responseBody.indexOf("\"session_id\":\"") + 14;
        int end = responseBody.indexOf("\"", start);
        return responseBody.substring(start, end);
    }
}
```

---

## Step 5: Update SSE Handler (1-2 hours)

**File:** `src/main/java/th/ac/kmitl/service/RefactorService.java`

Update the SSE event handler to detect confirmation events:

```java
package th.ac.kmitl.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import th.ac.kmitl.model.RefactorRequest;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Service
@RequiredArgsConstructor
public class RefactorService {

    private final PythonApiClient pythonApiClient;
    private final WebSocketService webSocketService;  // NEW: For sending confirmations to frontend
    
    private final Map<String, SseEmitter> activeEmitters = new ConcurrentHashMap<>();

    public String startRefactor(RefactorRequest request) {
        // Submit to Python API
        String sessionId = pythonApiClient.submitRefactor(request);
        
        // Start SSE listener in background
        listenToProgress(sessionId);
        
        return sessionId;
    }

    private void listenToProgress(String sessionId) {
        new Thread(() -> {
            try {
                String url = "http://localhost:8000/api/sessions/" + sessionId + "/stream";
                HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
                conn.setRequestMethod("GET");
                conn.setRequestProperty("Accept", "text/event-stream");

                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                String line;
                
                while ((line = reader.readLine()) != null) {
                    if (line.startsWith("event: ")) {
                        String eventType = line.substring(7);
                        String data = reader.readLine().substring(6);  // Skip "data: "
                        
                        handleSseEvent(sessionId, eventType, data);
                    }
                }
            } catch (Exception e) {
                log.error("SSE connection failed for session: {}", sessionId, e);
            }
        }).start();
    }

    private void handleSseEvent(String sessionId, String eventType, String data) {
        log.info("SSE Event [{}]: {}", eventType, data);
        
        // NEW: Handle confirmation events
        if ("confirmation_needed".equals(eventType)) {
            handleConfirmationNeeded(sessionId, eventType, data);
        } else if ("progress".equals(eventType)) {
            // Forward to frontend (existing logic)
            webSocketService.sendProgress(sessionId, data);
        } else if ("complete".equals(eventType)) {
            // Refactor completed (existing logic)
            webSocketService.sendComplete(sessionId, data);
        }
    }

    private void handleConfirmationNeeded(String sessionId, String confirmationType, String data) {
        log.info("Confirmation needed for session {}: type={}", sessionId, confirmationType);
        
        // Parse confirmation data
        // data format: {"confirmation_type": "plan", "plan_summary": "...", ...}
        
        // Send to frontend via WebSocket
        webSocketService.sendConfirmationRequest(sessionId, confirmationType, data);
    }
}
```

---

## Step 6: Create WebSocket Service (Optional, 1 hour)

If you want real-time frontend updates:

**File:** `src/main/java/th/ac/kmitl/service/WebSocketService.java`

```java
package th.ac.kmitl.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

@Slf4j
@Service
public class WebSocketService {

    private final SimpMessagingTemplate messagingTemplate;

    public WebSocketService(SimpMessagingTemplate messagingTemplate) {
        this.messagingTemplate = messagingTemplate;
    }

    public void sendProgress(String sessionId, String data) {
        String destination = "/topic/sessions/" + sessionId + "/progress";
        log.info("Sending progress to {}: {}", destination, data);
        messagingTemplate.convertAndSend(destination, data);
    }

    public void sendConfirmationRequest(String sessionId, String confirmationType, String data) {
        String destination = "/topic/sessions/" + sessionId + "/confirmations";
        log.info("Sending confirmation request to {}: type={}", destination, confirmationType);
        
        // Send to frontend - frontend shows modal
        messagingTemplate.convertAndSend(destination, Map.of(
            "type", confirmationType,
            "data", data
        ));
    }

    public void sendComplete(String sessionId, String data) {
        String destination = "/topic/sessions/" + sessionId + "/complete";
        log.info("Sending completion to {}: {}", destination, data);
        messagingTemplate.convertAndSend(destination, data);
    }
}
```

---

## Step 7: Testing (2 hours)

### 7.1 Unit Tests

**File:** `src/test/java/th/ac/kmitl/controller/ConfirmationControllerTest.java`

```java
package th.ac.kmitl.controller;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import th.ac.kmitl.model.ConfirmationResponse;
import th.ac.kmitl.service.PythonApiClient;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(ConfirmationController.class)
class ConfirmationControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private PythonApiClient pythonApiClient;

    @Test
    void testConfirmPlan_Approve() throws Exception {
        ConfirmationResponse mockResponse = new ConfirmationResponse();
        mockResponse.setStatus("resumed");
        mockResponse.setMessage("Plan approved");

        when(pythonApiClient.confirmPlan(eq("test-session"), any()))
                .thenReturn(mockResponse);

        mockMvc.perform(post("/api/sessions/test-session/confirm/plan")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"action\": \"approve\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("resumed"));
    }

    @Test
    void testConfirmPlan_NaturalLanguage() throws Exception {
        ConfirmationResponse mockResponse = new ConfirmationResponse();
        mockResponse.setStatus("waiting");
        mockResponse.setMessage("Processing modification");

        when(pythonApiClient.confirmPlan(eq("test-session"), any()))
                .thenReturn(mockResponse);

        mockMvc.perform(post("/api/sessions/test-session/confirm/plan")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"user_response\": \"yes but use Redis instead\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("waiting"));
    }
}
```

### 7.2 Manual Integration Test

```bash
# Terminal 1: Start Python API
cd RepoAI_AI
uv run python src/repoai/api/main.py

# Terminal 2: Start Java backend
cd repo-ai-backend
mvn spring-boot:run

# Terminal 3: Test flow
# 1. Submit refactor
curl -X POST http://localhost:8080/api/refactor \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test-user",
    "user_prompt": "Add JWT authentication",
    "mode": "interactive",
    "github_credentials": {
      "access_token": "YOUR_TOKEN",
      "repository_url": "https://github.com/yourusername/test-repo",
      "branch": "main"
    }
  }'

# Response: {"session_id": "abc123", ...}

# 2. Wait for confirmation_needed event (via SSE)

# 3. Confirm plan
curl -X POST http://localhost:8080/api/sessions/abc123/confirm/plan \
  -H "Content-Type: application/json" \
  -d '{"action": "approve"}'

# 4. Pipeline completes
```

---

## Configuration

### application.properties

```properties
# Python API configuration
python.api.url=http://localhost:8000

# WebSocket configuration (if using)
spring.websocket.allowed-origins=http://localhost:3000
```

---

## Troubleshooting

### Issue: "Connection refused to localhost:8000"
**Solution:** Make sure Python API is running:
```bash
cd RepoAI_AI
uv run python src/repoai/api/main.py
```

### Issue: "Session not found"
**Solution:** Check session exists:
```bash
curl http://localhost:8000/api/sessions/{sessionId}
```

### Issue: "Confirmation timeout"
**Solution:** Increase timeout in Python API `settings.py`:
```python
CONFIRMATION_TIMEOUT_SECONDS = 300  # 5 minutes
```

---

## Next Steps

1. ✅ Complete Java backend integration (this guide)
2. 🎨 Add frontend confirmation modal UI
3. 🧪 Test with real GitHub repository
4. 📚 Update API documentation
5. 🚀 Deploy for demo

**Estimated Total Time:** 4-6 hours  
**Demo Readiness After This:** 90%
