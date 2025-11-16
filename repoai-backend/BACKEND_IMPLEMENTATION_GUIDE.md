# Backend Implementation Guide for RepoAI

**Last Updated:** November 12, 2025  
**AI Service Status:** ✅ Complete and Production Ready  
**Backend Status:** ⚠️ Integration Layer Required

---

## 📋 Table of Contents

1. [AI Service Current Status](#ai-service-current-status)
2. [Critical TODOs in AI Service](#critical-todos-in-ai-service)
3. [Backend Implementation Phases](#backend-implementation-phases)
4. [API Contract Reference](#api-contract-reference)
5. [Database Schema Requirements](#database-schema-requirements)
6. [Testing Strategy](#testing-strategy)

---

## 🤖 AI Service Current Status

### ✅ Fully Implemented Features

The Python FastAPI AI service (`http://localhost:8000`) provides:

#### **REST Endpoints:**
- ✅ `POST /api/refactor` - Start refactoring job (returns session_id immediately)
- ✅ `GET /api/refactor/{session_id}` - Poll job status
- ✅ `GET /api/refactor/{session_id}/sse` - Server-Sent Events for real-time progress
- ✅ `WS /ws/refactor/{session_id}` - WebSocket for interactive mode
- ✅ `GET /api/health` - Health check
- ✅ `GET /api/health/ready` - Kubernetes readiness probe
- ✅ `GET /api/health/live` - Kubernetes liveness probe

#### **5-Agent Pipeline:**
1. ✅ **Intake Agent** - Parses user prompts into structured `JobSpec`
2. ✅ **Planner Agent** - Creates detailed `RefactorPlan` with risk assessment
3. ✅ **Transformer Agent** - Generates code changes with file-level streaming
4. ✅ **Validator Agent** - Validates with Maven/Gradle builds + tests
5. ✅ **PR Narrator Agent** - Creates PR descriptions (basic implementation)

#### **Infrastructure:**
- ✅ GitHub repository cloning (public/private repos)
- ✅ Maven/Gradle project validation
- ✅ Java AST parsing (javalang library)
- ✅ File-level streaming for real-time feedback
- ✅ Autonomous mode (background execution)
- ✅ Interactive mode (WebSocket with user confirmations)
- ✅ Comprehensive error handling and retries
- ✅ Model routing with fallbacks (Gemini 2.5 Pro/Flash)

---

## ⚠️ Critical TODOs in AI Service

These TODOs require **backend integration** to complete:

### 1. **Code Context / RAG Integration** (High Priority)

**Location:** `src/repoai/orchestrator/orchestrator_agent.py:201`

```python
intake_deps = IntakeDependencies(
    user_id=self.state.user_id,
    session_id=self.state.session_id,
    repository_url=self.deps.repository_url,
    code_context=None,  # TODO: Add code context from repo
)
```

**What's Needed:**
- AI service needs to receive **relevant code chunks** from backend's RAG system
- Backend should call its own `RAGController` to search for relevant context
- Pass this context in the refactor request or via a callback

**Backend Implementation Required:**
- Index repositories into Qdrant vector database
- Expose RAG search endpoint that AI service can call
- Alternatively, include code context in the initial refactor request

---

### 2. **PR Narrator Agent Enhancement** (Medium Priority)

**Location:** `src/repoai/orchestrator/orchestrator_agent.py:709`

```python
async def _run_narration_stage(self) -> None:
    # TODO: Implement PR Narrator Agent
    # For now, create a basic PR description
```

**Current Status:**
- Basic PR description generation works
- Uses template-based approach
- Could be enhanced with dedicated PR Narrator Agent (similar to other agents)

**Backend Impact:**
- Current implementation is sufficient for Phase 1
- Enhancement is nice-to-have, not blocking

---

### 3. **Validation Fix Instructions** (Low Priority)

**Location:** `src/repoai/orchestrator/orchestrator_agent.py:649`

```python
# TODO: Pass fix_instructions as additional context to Transformer
```

**Current Status:**
- Auto-fix validation errors works
- Could be enhanced to pass specific fix instructions to Transformer
- Currently regenerates code without specific instructions

**Backend Impact:**
- None - internal AI service optimization

---

## 🚀 Backend Implementation Phases

### **PHASE 1: AI Service Client Integration** ⚡ CRITICAL

**Goal:** Enable backend to communicate with AI service

#### Files to Create:

1. **`src/main/java/th/ac/mfu/repoai/services/AIServiceClient.java`**

**Purpose:** HTTP client for calling AI service

**Key Methods:**
```java
public class AIServiceClient {
    private final RestTemplate restTemplate;
    private final String aiServiceUrl; // http://localhost:8000
    
    // Start refactoring job
    public AIRefactorResponse startRefactor(AIRefactorRequest request);
    
    // Get job status (polling)
    public JobStatusResponse getStatus(String sessionId);
    
    // Check AI service health
    public HealthResponse checkHealth();
}
```

**Configuration:**
- Read `AI_SERVICE_URL` from `.env` (already added: `http://localhost:8000`)
- Set timeout to 5 minutes (`AI_SERVICE_TIMEOUT_MS=300000`)
- Use Spring's `RestTemplate` with `HttpComponentsClientHttpRequestFactory`

---

2. **`src/main/java/th/ac/mfu/repoai/domain/AIRefactorRequest.java`**

**Purpose:** DTO matching AI service's RefactorRequest model

**Fields:**
```java
public class AIRefactorRequest {
    private String userId;
    private String userPrompt;
    private GitHubCredentials githubCredentials;
    private String mode; // "autonomous" or "interactive"
    private Boolean autoFixEnabled;
    private Integer maxRetries;
    private Integer highRiskThreshold;
    private Float minTestCoverage;
    private Integer timeoutSeconds;
}

public class GitHubCredentials {
    private String accessToken;
    private String repositoryUrl;
    private String branch;
}
```

---

3. **`src/main/java/th/ac/mfu/repoai/domain/AIRefactorResponse.java`**

**Purpose:** DTO for AI service response

**Fields:**
```java
public class AIRefactorResponse {
    private String sessionId;      // "session_20251112_143022_abc123"
    private String status;          // "running"
    private String message;         // "Refactoring pipeline started"
    private String statusUrl;       // "/api/refactor/session_..."
    private String sseUrl;          // "/api/refactor/session_.../sse"
    private String websocketUrl;    // "/ws/refactor/session_..." (nullable)
}
```

---

4. **`src/main/java/th/ac/mfu/repoai/domain/RefactorJob.java`**

**Purpose:** Entity to track refactoring jobs in database

**Schema:**
```java
@Entity
@Table(name = "refactor_jobs")
public class RefactorJob {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(unique = true, nullable = false)
    private String sessionId; // From AI service
    
    @ManyToOne
    @JoinColumn(name = "conversation_id")
    private Conversation conversation;
    
    @ManyToOne
    @JoinColumn(name = "repository_id", referencedColumnName = "repoId")
    private Repository repository;
    
    @ManyToOne
    @JoinColumn(name = "user_id")
    private User user;
    
    @Enumerated(EnumType.STRING)
    private RefactorJobStatus status; // PENDING, RUNNING, COMPLETED, FAILED
    
    @Column(length = 2000)
    private String userPrompt;
    
    // Progress tracking
    private String currentStage;        // intake, planning, transformation, validation, narration
    private Float progressPercentage;   // 0.0 to 1.0
    private Long elapsedTimeMs;
    
    // Results summary
    private Integer filesChanged;
    private Boolean validationPassed;
    private String errorMessage;
    
    @Column(columnDefinition = "TEXT")
    private String resultJson; // Store final result as JSON
    
    @CreatedDate
    private LocalDateTime createdAt;
    
    @LastModifiedDate
    private LocalDateTime updatedAt;
}

public enum RefactorJobStatus {
    PENDING,
    RUNNING,
    COMPLETED,
    FAILED,
    CANCELLED
}
```

---

5. **`src/main/java/th/ac/mfu/repoai/controllers/RefactorJobController.java`**

**Purpose:** REST endpoints for starting and monitoring refactoring jobs

**Endpoints:**

```java
@RestController
@RequestMapping("/api/refactor")
public class RefactorJobController {
    
    @Autowired
    private AIServiceClient aiServiceClient;
    
    @Autowired
    private RefactorJobRepository refactorJobRepository;
    
    @Autowired
    private UserRepository userRepository;
    
    @Autowired
    private RepositoryRepository repositoryRepository;
    
    @Autowired
    private ConversationRepository conversationRepository;
    
    /**
     * Start a new refactoring job
     * POST /api/refactor/start
     */
    @PostMapping("/start")
    public ResponseEntity<RefactorJobResponse> startRefactor(
            Authentication auth,
            @RequestBody StartRefactorRequest request) {
        
        // 1. Authenticate user
        Long githubId = extractGithubId(auth);
        User user = userRepository.findByGithubId(githubId);
        
        // 2. Fetch repository and verify access
        Repository repo = repositoryRepository.findById(request.getRepositoryId());
        // Verify user owns or has access to repo
        
        // 3. Build GitHub credentials
        GitHubCredentials githubCreds = new GitHubCredentials(
            user.getGithubAccessToken(),  // Stored during OAuth
            repo.getHtmlUrl(),
            request.getBranch() != null ? request.getBranch() : repo.getDefaultBranch()
        );
        
        // 4. Build AI service request
        AIRefactorRequest aiRequest = new AIRefactorRequest(
            user.getId().toString(),
            request.getUserPrompt(),
            githubCreds,
            "autonomous",  // or from request
            true,          // auto_fix_enabled
            3,             // max_retries
            7,             // high_risk_threshold
            0.7f,          // min_test_coverage
            300            // timeout_seconds
        );
        
        // 5. Call AI service
        AIRefactorResponse aiResponse = aiServiceClient.startRefactor(aiRequest);
        
        // 6. Save job to database
        RefactorJob job = new RefactorJob();
        job.setSessionId(aiResponse.getSessionId());
        job.setUser(user);
        job.setRepository(repo);
        if (request.getConversationId() != null) {
            Conversation convo = conversationRepository.findById(request.getConversationId());
            job.setConversation(convo);
        }
        job.setUserPrompt(request.getUserPrompt());
        job.setStatus(RefactorJobStatus.RUNNING);
        job.setProgressPercentage(0.0f);
        job.setCurrentStage("idle");
        
        refactorJobRepository.save(job);
        
        // 7. Return response
        return ResponseEntity.ok(new RefactorJobResponse(
            job.getId(),
            aiResponse.getSessionId(),
            aiResponse.getStatus(),
            aiResponse.getMessage(),
            "/api/refactor/" + job.getId() + "/status",
            "/api/refactor/" + job.getId() + "/stream"
        ));
    }
    
    /**
     * Get job status
     * GET /api/refactor/{jobId}/status
     */
    @GetMapping("/{jobId}/status")
    public ResponseEntity<RefactorJobStatusDTO> getJobStatus(
            Authentication auth,
            @PathVariable Long jobId) {
        
        RefactorJob job = refactorJobRepository.findById(jobId);
        // Verify user owns this job
        
        return ResponseEntity.ok(RefactorJobStatusDTO.from(job));
    }
    
    /**
     * Get job result
     * GET /api/refactor/{jobId}/result
     */
    @GetMapping("/{jobId}/result")
    public ResponseEntity<RefactorResultDTO> getJobResult(
            Authentication auth,
            @PathVariable Long jobId) {
        
        RefactorJob job = refactorJobRepository.findById(jobId);
        // Verify user owns this job
        
        if (job.getStatus() != RefactorJobStatus.COMPLETED) {
            return ResponseEntity.status(202).build(); // Accepted, not ready yet
        }
        
        // Parse resultJson and return
        RefactorResultDTO result = parseResultJson(job.getResultJson());
        return ResponseEntity.ok(result);
    }
}
```

---

### **PHASE 2: SSE Progress Streaming** ⚡ HIGH PRIORITY

**Goal:** Stream real-time progress from AI service to frontend

#### Implementation Options:

**Option A: Backend Proxies SSE from AI Service** (Recommended)

Create `AIServiceSSEListener.java` that:
1. Connects to AI service SSE endpoint: `GET http://localhost:8000/api/refactor/{session_id}/sse`
2. Consumes SSE events using Spring WebFlux `WebClient`
3. Updates `RefactorJob` in database with progress
4. Re-broadcasts events to frontend clients

**Option B: Frontend Connects Directly to AI Service**

Simpler but requires CORS configuration and direct network access to AI service.

#### Recommended: Option A - Backend Proxy

**File:** `src/main/java/th/ac/mfu/repoai/services/AIServiceSSEListener.java`

```java
@Service
public class AIServiceSSEListener {
    
    @Autowired
    private WebClient.Builder webClientBuilder;
    
    @Autowired
    private RefactorJobRepository refactorJobRepository;
    
    public Flux<ServerSentEvent<String>> streamProgress(String sessionId) {
        
        String sseUrl = aiServiceUrl + "/api/refactor/" + sessionId + "/sse";
        
        return webClientBuilder.build()
            .get()
            .uri(sseUrl)
            .retrieve()
            .bodyToFlux(ServerSentEvent.class)
            .doOnNext(event -> {
                // Update database with progress
                updateJobProgress(sessionId, event);
            })
            .onErrorResume(error -> {
                log.error("SSE connection error: " + error.getMessage());
                return Flux.empty();
            });
    }
    
    private void updateJobProgress(String sessionId, ServerSentEvent event) {
        RefactorJob job = refactorJobRepository.findBySessionId(sessionId);
        if (job != null) {
            // Parse event data and update job
            ProgressUpdate update = parseProgressUpdate(event.data());
            job.setCurrentStage(update.getStage());
            job.setProgressPercentage(update.getProgress());
            job.setElapsedTimeMs(update.getElapsedTimeMs());
            
            // Check if completed
            if ("complete".equals(update.getStatus())) {
                job.setStatus(RefactorJobStatus.COMPLETED);
                fetchAndStoreResult(sessionId, job);
            } else if ("failed".equals(update.getStatus())) {
                job.setStatus(RefactorJobStatus.FAILED);
                job.setErrorMessage(update.getMessage());
            }
            
            refactorJobRepository.save(job);
        }
    }
}
```

#### Add SSE Endpoint in Controller:

```java
/**
 * Stream progress updates
 * GET /api/refactor/{jobId}/stream
 */
@GetMapping(value = "/{jobId}/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public Flux<ServerSentEvent<String>> streamJobProgress(
        Authentication auth,
        @PathVariable Long jobId) {
    
    RefactorJob job = refactorJobRepository.findById(jobId);
    // Verify user owns this job
    
    return aiServiceSSEListener.streamProgress(job.getSessionId());
}
```

---

### **PHASE 3: Result Storage** 📦 HIGH PRIORITY

**Goal:** Store refactoring results in database for later retrieval

#### Option 1: Store as JSON (Simple)

Add to `RefactorJob` entity:
```java
@Column(columnDefinition = "TEXT")
private String resultJson; // Store entire result as JSON
```

#### Option 2: Normalized Storage (Better for queries)

**File:** `src/main/java/th/ac/mfu/repoai/domain/CodeChange.java`

```java
@Entity
@Table(name = "code_changes")
public class CodeChange {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @ManyToOne
    @JoinColumn(name = "refactor_job_id", nullable = false)
    private RefactorJob refactorJob;
    
    @Column(nullable = false, length = 1000)
    private String filePath;
    
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ChangeType changeType; // CREATE, UPDATE, DELETE
    
    @Column(columnDefinition = "TEXT")
    private String oldContent;
    
    @Column(columnDefinition = "TEXT")
    private String newContent;
    
    @Column(columnDefinition = "TEXT")
    private String explanation;
    
    private Integer linesAdded;
    private Integer linesRemoved;
    
    @CreatedDate
    private LocalDateTime createdAt;
}

public enum ChangeType {
    CREATE,
    UPDATE,
    DELETE,
    RENAME
}
```

#### Fetch and Store Result:

```java
private void fetchAndStoreResult(String sessionId, RefactorJob job) {
    // Call AI service to get final result
    String resultUrl = aiServiceUrl + "/api/refactor/" + sessionId;
    JobStatusResponse finalStatus = restTemplate.getForObject(resultUrl, JobStatusResponse.class);
    
    if (finalStatus != null && finalStatus.getResult() != null) {
        // Option 1: Store as JSON
        job.setResultJson(objectMapper.writeValueAsString(finalStatus.getResult()));
        
        // Option 2: Parse and store as entities
        PipelineResult result = finalStatus.getResult();
        if (result.getCodeChanges() != null) {
            for (CodeChangeDTO changeDto : result.getCodeChanges()) {
                CodeChange change = new CodeChange();
                change.setRefactorJob(job);
                change.setFilePath(changeDto.getFilePath());
                change.setChangeType(ChangeType.valueOf(changeDto.getChangeType()));
                change.setOldContent(changeDto.getOldContent());
                change.setNewContent(changeDto.getNewContent());
                change.setExplanation(changeDto.getExplanation());
                change.setLinesAdded(changeDto.getLinesAdded());
                change.setLinesRemoved(changeDto.getLinesRemoved());
                
                codeChangeRepository.save(change);
            }
        }
        
        job.setFilesChanged(result.getCodeChanges().size());
        job.setValidationPassed(result.getValidationPassed());
    }
    
    refactorJobRepository.save(job);
}
```

---

### **PHASE 4: Chat Integration** 💬 MEDIUM PRIORITY

**Goal:** Link refactoring jobs to conversation history

#### Update ChatController:

**New Endpoint:** `POST /api/conversations/{convoId}/refactor`

```java
@PostMapping("/{convoId}/refactor")
public ResponseEntity<RefactorJobResponse> startRefactorFromChat(
        Authentication auth,
        @PathVariable Long convoId,
        @RequestBody ChatRefactorRequest request) {
    
    // 1. Verify conversation ownership
    Conversation convo = conversationRepository.findById(convoId);
    // Verify user owns conversation
    
    // 2. Create Chat message with user prompt
    Chat userMessage = new Chat();
    userMessage.setConversation(convo);
    userMessage.setContent(request.getUserPrompt());
    userMessage.setRole("user");
    chatRepository.save(userMessage);
    
    // 3. Start refactoring job (call RefactorJobController logic)
    StartRefactorRequest refactorRequest = new StartRefactorRequest(
        convo.getRepository().getRepoId(),
        request.getUserPrompt(),
        convo.getBranch() != null ? convo.getBranch().getName() : null,
        convoId
    );
    
    RefactorJobResponse jobResponse = startRefactor(auth, refactorRequest);
    
    // 4. Create system message indicating job started
    Chat systemMessage = new Chat();
    systemMessage.setConversation(convo);
    systemMessage.setContent("🚀 Refactoring job started: " + jobResponse.getSessionId());
    systemMessage.setRole("system");
    systemMessage.setMetadataJson(objectMapper.writeValueAsString(Map.of(
        "session_id", jobResponse.getSessionId(),
        "job_id", jobResponse.getJobId(),
        "type", "refactor_started"
    )));
    chatRepository.save(systemMessage);
    
    // 5. Update conversation's last_message_at
    convo.setLastMessageAt(LocalDateTime.now());
    conversationRepository.save(convo);
    
    return ResponseEntity.ok(jobResponse);
}
```

#### Background Job Completion Handler:

Create `@Scheduled` task or event listener:

```java
@Service
public class RefactorJobCompletionHandler {
    
    @EventListener
    public void handleJobCompletion(RefactorJobCompletedEvent event) {
        RefactorJob job = event.getJob();
        
        if (job.getConversation() != null) {
            // Create AI response message
            Chat aiMessage = new Chat();
            aiMessage.setConversation(job.getConversation());
            aiMessage.setRole("assistant");
            
            if (job.getStatus() == RefactorJobStatus.COMPLETED) {
                aiMessage.setContent(
                    "✅ Refactoring completed successfully!\n\n" +
                    "**Summary:**\n" +
                    "- Files modified: " + job.getFilesChanged() + "\n" +
                    "- Validation: " + (job.getValidationPassed() ? "Passed" : "Failed") + "\n" +
                    "- Duration: " + (job.getElapsedTimeMs() / 1000) + "s\n\n" +
                    "View details: [Job #" + job.getId() + "](/refactor/" + job.getId() + ")"
                );
            } else {
                aiMessage.setContent(
                    "❌ Refactoring failed: " + job.getErrorMessage()
                );
            }
            
            aiMessage.setMetadataJson(objectMapper.writeValueAsString(Map.of(
                "session_id", job.getSessionId(),
                "job_id", job.getId(),
                "type", "refactor_completed",
                "status", job.getStatus().toString()
            )));
            
            chatRepository.save(aiMessage);
            
            // Update conversation
            job.getConversation().setLastMessageAt(LocalDateTime.now());
            conversationRepository.save(job.getConversation());
        }
    }
}
```

---

### **PHASE 5: RAG Integration** 🧠 HIGH PRIORITY (Quality)

**Goal:** Provide code context to AI service for better refactoring

#### What AI Service Needs:

When planning a refactor, the AI service needs **relevant code snippets** from the repository:
- Related classes/interfaces
- Dependency usage examples
- Similar patterns in the codebase
- Configuration files

#### Two Approaches:

**Approach A: AI Service Calls Backend RAG Endpoint** (Recommended)

1. Backend indexes repositories into Qdrant
2. Backend exposes `POST /api/rag/search-for-ai` endpoint
3. AI service calls this endpoint during planning stage
4. Backend returns relevant code chunks

**Approach B: Backend Includes Context in Initial Request**

1. Backend performs RAG search upfront
2. Includes relevant code in `AIRefactorRequest`
3. Simpler but less flexible

#### Implementation: Approach A

**Step 1: Complete Repository Indexing**

Update `RepositoryIndexingService.java` (currently has TODO):

```java
@Service
public class RepositoryIndexingService {
    
    @Autowired
    private AIServiceClient aiServiceClient;
    
    @Autowired
    private ContextChunkRepository contextChunkRepository;
    
    @Autowired
    private RestTemplate restTemplate;
    
    @Value("${qdrant.url:http://localhost:6333}")
    private String qdrantUrl;
    
    public void indexRepository(Long repoId, String accessToken) {
        Repository repo = repositoryRepository.findById(repoId);
        
        // 1. Clone repository locally
        Path repoPath = cloneRepository(repo.getHtmlUrl(), accessToken);
        
        // 2. Parse Java files into chunks
        List<CodeChunk> chunks = parseJavaFiles(repoPath);
        
        // 3. Generate embeddings via AI service
        List<String> texts = chunks.stream()
            .map(CodeChunk::getContent)
            .collect(Collectors.toList());
        
        EmbeddingResponse embeddingResponse = aiServiceClient.generateEmbeddings(texts);
        List<List<Float>> embeddings = embeddingResponse.getEmbeddings();
        
        // 4. Store in Qdrant
        for (int i = 0; i < chunks.size(); i++) {
            CodeChunk chunk = chunks.get(i);
            List<Float> embedding = embeddings.get(i);
            
            // Store in MySQL
            ContextChunk contextChunk = new ContextChunk();
            contextChunk.setRepoId(repoId);
            contextChunk.setFilePath(chunk.getFilePath());
            contextChunk.setChunkText(chunk.getContent());
            contextChunk.setStartLine(chunk.getStartLine());
            contextChunk.setEndLine(chunk.getEndLine());
            contextChunk = contextChunkRepository.save(contextChunk);
            
            // Store in Qdrant
            storeInQdrant(contextChunk.getChunkId(), embedding, repoId, chunk.getFilePath());
        }
        
        log.info("Indexed {} chunks for repo {}", chunks.size(), repoId);
    }
    
    private List<CodeChunk> parseJavaFiles(Path repoPath) {
        // Use JavaParser to parse Java files
        // Split into semantic chunks (classes, methods, etc.)
        // Return list of chunks with content, file path, line numbers
    }
    
    private void storeInQdrant(Long chunkId, List<Float> embedding, Long repoId, String filePath) {
        String url = qdrantUrl + "/collections/code_chunks/points";
        
        Map<String, Object> point = Map.of(
            "id", chunkId,
            "vector", embedding,
            "payload", Map.of(
                "repo_id", repoId,
                "file_path", filePath,
                "chunk_id", chunkId
            )
        );
        
        restTemplate.postForEntity(url, Map.of("points", List.of(point)), String.class);
    }
}
```

**Step 2: Add Embedding Endpoint to AI Service**

**AI Service TODO:** Create embedding endpoint

```python
# In src/repoai/api/routes/embeddings.py (NEW FILE)

@router.post("/embeddings/encode")
async def encode_texts(request: EmbeddingRequest) -> EmbeddingResponse:
    """
    Generate embeddings for text chunks.
    
    Used by backend for RAG indexing.
    """
    texts = request.texts
    
    # Use Gemini embedding model
    embeddings = []
    for text in texts:
        embedding = await generate_embedding(text)
        embeddings.append(embedding)
    
    return EmbeddingResponse(embeddings=embeddings)
```

**Step 3: Expose RAG Search for AI Service**

Update `RAGController.java`:

```java
/**
 * Search for relevant code chunks (called by AI service)
 * POST /api/rag/search-for-ai
 */
@PostMapping("/search-for-ai")
public ResponseEntity<AIRAGSearchResponse> searchForAI(
        @RequestHeader("X-AI-Service-Key") String apiKey,
        @RequestBody AIRAGSearchRequest request) {
    
    // Validate API key
    if (!apiKey.equals(aiServiceApiKey)) {
        return ResponseEntity.status(403).build();
    }
    
    Long repoId = request.getRepoId();
    String query = request.getQuery();
    Integer topK = request.getTopK() != null ? request.getTopK() : 10;
    
    // 1. Generate embedding for query (call AI service)
    EmbeddingResponse embeddingResponse = aiServiceClient.generateEmbeddings(List.of(query));
    List<Float> queryVector = embeddingResponse.getEmbeddings().get(0);
    
    // 2. Search Qdrant
    List<QdrantSearchResult> qdrantResults = searchQdrant(queryVector, repoId, topK);
    
    // 3. Fetch chunk text from MySQL
    List<Long> chunkIds = qdrantResults.stream()
        .map(QdrantSearchResult::getChunkId)
        .collect(Collectors.toList());
    
    List<ContextChunk> chunks = contextChunkRepository.findByChunkIdIn(chunkIds);
    
    // 4. Build response
    List<CodeChunkResult> results = new ArrayList<>();
    for (QdrantSearchResult qdrantResult : qdrantResults) {
        ContextChunk chunk = chunks.stream()
            .filter(c -> c.getChunkId().equals(qdrantResult.getChunkId()))
            .findFirst()
            .orElse(null);
        
        if (chunk != null) {
            results.add(new CodeChunkResult(
                chunk.getFilePath(),
                chunk.getChunkText(),
                qdrantResult.getScore(),
                chunk.getStartLine(),
                chunk.getEndLine()
            ));
        }
    }
    
    return ResponseEntity.ok(new AIRAGSearchResponse(results));
}
```

**Step 4: Update AI Service to Call Backend RAG**

**AI Service TODO:** In planner agent, add RAG retrieval:

```python
# In src/repoai/agents/planner_agent.py

async def run_planner_agent(
    job_spec: JobSpec,
    dependencies: PlannerDependencies,
    adapter: PydanticAIAdapter | None = None,
) -> tuple[RefactorPlan, RefactorMetadata]:
    
    # NEW: Retrieve relevant code context from backend
    if dependencies.repository_url:
        code_context = await retrieve_code_context(
            repository_id=dependencies.repository_id,
            query=job_spec.user_prompt,
            backend_url="http://localhost:8081"  # From env
        )
    else:
        code_context = []
    
    # Include code_context in planner prompt
    ...
```

---

### **PHASE 6: Error Handling & Monitoring** 🛡️ MEDIUM PRIORITY

#### 1. AI Service Health Checker

```java
@Service
public class AIServiceHealthChecker {
    
    @Scheduled(fixedRate = 60000) // Every minute
    public void checkAIServiceHealth() {
        try {
            HealthResponse health = aiServiceClient.checkHealth();
            if (!"healthy".equals(health.getStatus())) {
                log.warn("AI service is degraded: " + health.getStatus());
                // Alert ops team
            }
        } catch (Exception e) {
            log.error("AI service is down: " + e.getMessage());
            // Alert ops team
        }
    }
}
```

#### 2. Retry Logic

```java
@Service
public class AIServiceClient {
    
    @Retryable(
        value = {RestClientException.class},
        maxAttempts = 3,
        backoff = @Backoff(delay = 2000, multiplier = 2)
    )
    public AIRefactorResponse startRefactor(AIRefactorRequest request) {
        return restTemplate.postForObject(
            aiServiceUrl + "/api/refactor",
            request,
            AIRefactorResponse.class
        );
    }
}
```

#### 3. Job Cleanup Service

```java
@Service
public class RefactorJobCleanupService {
    
    @Scheduled(cron = "0 0 2 * * *") // Daily at 2 AM
    public void cleanupOldJobs() {
        LocalDateTime cutoff = LocalDateTime.now().minusDays(30);
        List<RefactorJob> oldJobs = refactorJobRepository.findByCreatedAtBefore(cutoff);
        
        for (RefactorJob job : oldJobs) {
            // Archive to cold storage
            archiveJob(job);
            
            // Delete from main database
            refactorJobRepository.delete(job);
        }
        
        log.info("Cleaned up {} old refactor jobs", oldJobs.size());
    }
}
```

---

### **PHASE 7: GitHub PR Automation** 🔀 LOW PRIORITY (High Value)

**Goal:** Automatically create GitHub PRs from refactoring results

#### Implementation:

```java
@Service
public class GitHubPRService {
    
    @Autowired
    private GitServices gitServices;
    
    public PullRequestResponse createPRFromRefactorJob(Long jobId, String branchName) {
        RefactorJob job = refactorJobRepository.findById(jobId);
        
        // 1. Create branch
        String baseBranch = job.getRepository().getDefaultBranch();
        gitServices.createBranch(
            job.getRepository().getFullName(),
            branchName,
            baseBranch,
            job.getUser().getGithubAccessToken()
        );
        
        // 2. Apply code changes
        List<CodeChange> changes = codeChangeRepository.findByRefactorJob(job);
        for (CodeChange change : changes) {
            String filePath = change.getFilePath();
            String newContent = change.getNewContent();
            
            // Commit file change
            gitServices.updateFile(
                job.getRepository().getFullName(),
                branchName,
                filePath,
                newContent,
                "refactor: " + change.getExplanation(),
                job.getUser().getGithubAccessToken()
            );
        }
        
        // 3. Create pull request
        String prTitle = "feat: " + job.getUserPrompt();
        String prBody = generatePRDescription(job);
        
        PullRequestResponse pr = gitServices.createPullRequest(
            job.getRepository().getFullName(),
            prTitle,
            prBody,
            branchName,
            baseBranch,
            job.getUser().getGithubAccessToken()
        );
        
        // 4. Store PR info in job
        job.setMetadataJson(objectMapper.writeValueAsString(Map.of(
            "pr_number", pr.getNumber(),
            "pr_url", pr.getUrl(),
            "branch_name", branchName
        )));
        refactorJobRepository.save(job);
        
        return pr;
    }
    
    private String generatePRDescription(RefactorJob job) {
        // Parse AI-generated PR description from resultJson
        // Or generate a summary
        return "## Summary\n\n" +
               job.getUserPrompt() + "\n\n" +
               "## Changes\n\n" +
               "- Files modified: " + job.getFilesChanged() + "\n" +
               "- Validation: " + (job.getValidationPassed() ? "✅ Passed" : "❌ Failed") + "\n\n" +
               "## Details\n\n" +
               "This PR was automatically generated by RepoAI.\n" +
               "Session ID: `" + job.getSessionId() + "`";
    }
}
```

Add endpoint:

```java
/**
 * Apply refactoring result and create PR
 * POST /api/refactor/{jobId}/apply
 */
@PostMapping("/{jobId}/apply")
public ResponseEntity<PRApplicationResponse> applyRefactoring(
        Authentication auth,
        @PathVariable Long jobId,
        @RequestBody ApplyRefactoringRequest request) {
    
    RefactorJob job = refactorJobRepository.findById(jobId);
    // Verify ownership and completion status
    
    String branchName = request.getBranchName() != null 
        ? request.getBranchName()
        : "repoai/" + job.getSessionId();
    
    PullRequestResponse pr = gitHubPRService.createPRFromRefactorJob(jobId, branchName);
    
    return ResponseEntity.ok(new PRApplicationResponse(
        pr.getNumber(),
        pr.getUrl(),
        branchName
    ));
}
```

---

### **PHASE 8: Security & Production** 🔒 CRITICAL

#### 1. API Authentication

**AI Service:** Add API key validation

```python
# In AI service
from fastapi import Header, HTTPException

async def verify_backend_token(x_api_key: str = Header(...)):
    if x_api_key != os.getenv("BACKEND_API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")

# Add to endpoints
@router.post("/refactor", dependencies=[Depends(verify_backend_token)])
```

**Backend:** Send API key in requests

```java
// In .env
BACKEND_API_KEY=generate_random_secure_key_here

// In AIServiceClient
HttpHeaders headers = new HttpHeaders();
headers.set("X-API-Key", backendApiKey);
HttpEntity<AIRefactorRequest> entity = new HttpEntity<>(request, headers);
```

#### 2. Rate Limiting

```java
@Service
public class RefactorRateLimiter {
    
    private final LoadingCache<Long, Integer> requestCounts;
    
    public RefactorRateLimiter() {
        this.requestCounts = CacheBuilder.newBuilder()
            .expireAfterWrite(1, TimeUnit.HOURS)
            .build(new CacheLoader<Long, Integer>() {
                @Override
                public Integer load(Long userId) {
                    return 0;
                }
            });
    }
    
    public boolean allowRequest(Long userId) {
        try {
            int count = requestCounts.get(userId);
            if (count >= 10) { // 10 requests per hour
                return false;
            }
            requestCounts.put(userId, count + 1);
            return true;
        } catch (Exception e) {
            return true; // Fail open
        }
    }
}
```

#### 3. Input Validation

```java
@PostMapping("/start")
public ResponseEntity<?> startRefactor(
        Authentication auth,
        @Valid @RequestBody StartRefactorRequest request) {
    
    // Validate user owns repository
    if (!userOwnsRepository(auth, request.getRepositoryId())) {
        return ResponseEntity.status(403).body("Access denied");
    }
    
    // Validate prompt length
    if (request.getUserPrompt().length() > 5000) {
        return ResponseEntity.badRequest().body("Prompt too long");
    }
    
    // Rate limiting
    Long userId = extractUserId(auth);
    if (!rateLimiter.allowRequest(userId)) {
        return ResponseEntity.status(429).body("Rate limit exceeded");
    }
    
    // Continue...
}
```

#### 4. Database Indexes

```sql
-- Add indexes for performance
CREATE INDEX idx_refactor_job_session_id ON refactor_jobs(session_id);
CREATE INDEX idx_refactor_job_user_id ON refactor_jobs(user_id);
CREATE INDEX idx_refactor_job_status ON refactor_jobs(status);
CREATE INDEX idx_refactor_job_created_at ON refactor_jobs(created_at);
CREATE INDEX idx_code_change_job_id ON code_changes(refactor_job_id);
```

---

## 📄 API Contract Reference

### AI Service → Backend Requests (To Implement)

These are calls the AI service will make TO the backend:

#### 1. RAG Search for Code Context

**Endpoint:** `POST http://localhost:8081/api/rag/search-for-ai`

**Request:**
```json
{
  "repo_id": 12345,
  "query": "JWT authentication implementation",
  "top_k": 10
}
```

**Response:**
```json
{
  "results": [
    {
      "file_path": "src/main/java/com/example/auth/JwtService.java",
      "content": "public class JwtService { ... }",
      "score": 0.92,
      "start_line": 15,
      "end_line": 45
    }
  ]
}
```

**When to Implement:** Phase 5 (RAG Integration)

#### 2. Generate Embeddings

**Endpoint:** `POST http://localhost:8000/api/embeddings/encode`

**Request:**
```json
{
  "texts": [
    "public class UserService { ... }",
    "public interface AuthRepository { ... }"
  ]
}
```

**Response:**
```json
{
  "embeddings": [
    [0.123, 0.456, 0.789, ...],
    [0.234, 0.567, 0.890, ...]
  ]
}
```

**Status:** ⚠️ TODO in AI service (Phase 5)

---

### Backend → AI Service Requests

These are calls the backend makes TO the AI service:

#### 1. Start Refactoring Job ✅

**Endpoint:** `POST http://localhost:8000/api/refactor`

**Request:**
```json
{
  "user_id": "123",
  "user_prompt": "Add JWT authentication to UserService",
  "github_credentials": {
    "access_token": "ghp_xxxxxxxxxxxx",
    "repository_url": "https://github.com/user/repo",
    "branch": "main"
  },
  "mode": "autonomous",
  "auto_fix_enabled": true,
  "max_retries": 3,
  "high_risk_threshold": 7,
  "min_test_coverage": 0.7,
  "timeout_seconds": 300
}
```

**Response:**
```json
{
  "session_id": "session_20251112_143022_abc123",
  "status": "running",
  "message": "Refactoring pipeline started",
  "status_url": "/api/refactor/session_20251112_143022_abc123",
  "sse_url": "/api/refactor/session_20251112_143022_abc123/sse",
  "websocket_url": null
}
```

**Status:** ✅ Fully implemented in AI service

---

#### 2. Get Job Status ✅

**Endpoint:** `GET http://localhost:8000/api/refactor/{session_id}`

**Response:**
```json
{
  "session_id": "session_20251112_143022_abc123",
  "user_id": "123",
  "stage": "transformation",
  "status": "running",
  "progress": 0.6,
  "message": "Generating code changes...",
  "elapsed_time_ms": 45000,
  "job_id": "job_abc123",
  "plan_id": "plan_xyz789",
  "files_changed": 3,
  "validation_passed": false,
  "errors": [],
  "warnings": ["High complexity detected"],
  "retry_count": 0,
  "result": null
}
```

**Status:** ✅ Fully implemented in AI service

---

#### 3. Stream Progress (SSE) ✅

**Endpoint:** `GET http://localhost:8000/api/refactor/{session_id}/sse`

**Stream Output:**
```
event: progress
data: {"session_id":"session_...","stage":"intake","status":"in_progress","progress":0.2,"message":"Parsing user request...","elapsed_time_ms":2000}

event: progress
data: {"session_id":"session_...","stage":"planning","status":"in_progress","progress":0.4,"message":"Creating refactoring plan...","elapsed_time_ms":15000}

event: progress
data: {"session_id":"session_...","stage":"transformation","status":"in_progress","progress":0.6,"message":"Generating code...","elapsed_time_ms":30000}

event: progress
data: {"session_id":"session_...","stage":"complete","status":"complete","progress":1.0,"message":"Refactoring completed!","elapsed_time_ms":60000}
```

**Status:** ✅ Fully implemented in AI service

---

#### 4. Health Check ✅

**Endpoint:** `GET http://localhost:8000/api/health`

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "services": {
    "gemini_api": "configured",
    "config": "loaded"
  }
}
```

**Status:** ✅ Fully implemented in AI service

---

## 📊 Database Schema Requirements

### New Tables to Create:

#### 1. `refactor_jobs`

```sql
CREATE TABLE refactor_jobs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    conversation_id BIGINT,
    repository_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    user_prompt TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    current_stage VARCHAR(50),
    progress_percentage FLOAT,
    elapsed_time_ms BIGINT,
    files_changed INT,
    validation_passed BOOLEAN,
    error_message TEXT,
    result_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_repository_id (repository_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    
    FOREIGN KEY (conversation_id) REFERENCES conversation(id) ON DELETE SET NULL,
    FOREIGN KEY (repository_id) REFERENCES repositories(repoId) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

#### 2. `code_changes` (Optional)

```sql
CREATE TABLE code_changes (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    refactor_job_id BIGINT NOT NULL,
    file_path VARCHAR(1000) NOT NULL,
    change_type VARCHAR(50) NOT NULL,
    old_content TEXT,
    new_content TEXT,
    explanation TEXT,
    lines_added INT,
    lines_removed INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_job_id (refactor_job_id),
    INDEX idx_file_path (file_path(255)),
    
    FOREIGN KEY (refactor_job_id) REFERENCES refactor_jobs(id) ON DELETE CASCADE
);
```

---

## 🧪 Testing Strategy

### Phase 1: Unit Tests

Test individual services in isolation:

```java
@SpringBootTest
class AIServiceClientTest {
    
    @Autowired
    private AIServiceClient client;
    
    @MockBean
    private RestTemplate restTemplate;
    
    @Test
    void testStartRefactor_Success() {
        // Mock RestTemplate response
        AIRefactorResponse mockResponse = new AIRefactorResponse();
        mockResponse.setSessionId("session_test_123");
        mockResponse.setStatus("running");
        
        when(restTemplate.postForObject(any(), any(), eq(AIRefactorResponse.class)))
            .thenReturn(mockResponse);
        
        // Call service
        AIRefactorRequest request = new AIRefactorRequest();
        request.setUserId("123");
        request.setUserPrompt("Add logging");
        
        AIRefactorResponse response = client.startRefactor(request);
        
        // Verify
        assertNotNull(response);
        assertEquals("session_test_123", response.getSessionId());
        assertEquals("running", response.getStatus());
    }
}
```

### Phase 2: Integration Tests

Test backend ↔ AI service communication:

```java
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@TestPropertySource(properties = {
    "AI_SERVICE_URL=http://localhost:8000"
})
class RefactorJobControllerIntegrationTest {
    
    @Autowired
    private TestRestTemplate restTemplate;
    
    @Test
    void testStartRefactor_EndToEnd() {
        // Prepare request
        StartRefactorRequest request = new StartRefactorRequest();
        request.setRepositoryId(123L);
        request.setUserPrompt("Add JWT authentication");
        
        // Call endpoint
        ResponseEntity<RefactorJobResponse> response = restTemplate
            .withBasicAuth("test_user", "password")
            .postForEntity("/api/refactor/start", request, RefactorJobResponse.class);
        
        // Verify
        assertEquals(HttpStatus.OK, response.getStatusCode());
        assertNotNull(response.getBody().getSessionId());
        assertTrue(response.getBody().getSessionId().startsWith("session_"));
        
        // Wait for job to start
        Thread.sleep(2000);
        
        // Check status
        ResponseEntity<RefactorJobStatusDTO> statusResponse = restTemplate
            .withBasicAuth("test_user", "password")
            .getForEntity("/api/refactor/" + response.getBody().getJobId() + "/status",
                RefactorJobStatusDTO.class);
        
        assertEquals(HttpStatus.OK, statusResponse.getStatusCode());
        assertEquals("running", statusResponse.getBody().getStatus());
    }
}
```

### Phase 3: E2E Tests

Test full workflow with real repositories:

```java
@Test
void testCompleteRefactorWorkflow() {
    // 1. Start refactor job
    RefactorJobResponse job = startRefactorJob("Add error handling to UserService");
    
    // 2. Monitor progress via SSE
    WebClient client = WebClient.create("http://localhost:8081");
    Flux<ServerSentEvent<String>> events = client.get()
        .uri("/api/refactor/" + job.getJobId() + "/stream")
        .retrieve()
        .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() {});
    
    // 3. Wait for completion
    String finalStatus = events
        .filter(event -> "complete".equals(parseStatus(event)))
        .blockFirst(Duration.ofMinutes(5))
        .data();
    
    // 4. Verify result
    RefactorResultDTO result = getRefactorResult(job.getJobId());
    assertTrue(result.getFilesChanged() > 0);
    assertTrue(result.getValidationPassed());
}
```

---

## 📦 Summary: What Backend Needs to Do

### Immediate (Phase 1-3):
1. ✅ Create `.env` file (DONE)
2. ❌ Create `AIServiceClient.java` service
3. ❌ Create `RefactorJob` entity and repository
4. ❌ Create `RefactorJobController` with `/start` endpoint
5. ❌ Create `AIServiceSSEListener` for progress streaming
6. ❌ Add result storage (JSON or normalized)

### Soon (Phase 4-5):
7. ❌ Integrate with `ChatController`
8. ❌ Complete `RepositoryIndexingService` (parse Java files)
9. ❌ Add embedding generation endpoint to AI service
10. ❌ Expose RAG search endpoint for AI service
11. ❌ Update AI service planner to use RAG context

### Later (Phase 6-8):
12. ❌ Add health checking and monitoring
13. ❌ Add retry logic and error handling
14. ❌ Create GitHub PR automation
15. ❌ Add authentication between services
16. ❌ Add rate limiting
17. ❌ Add database indexes

---

## 🎯 Next Steps for Backend Team

**Week 1 Priority:**
1. Start MySQL database
2. Create `RefactorJob` entity and migration
3. Create `AIServiceClient` service
4. Create `RefactorJobController` with `/start` endpoint
5. Test basic integration (start job, get status)

**Week 2 Priority:**
1. Add SSE streaming proxy
2. Store results in database
3. Link to conversation/chat
4. Basic testing

**Week 3+ Priority:**
1. RAG integration
2. GitHub PR automation
3. Production hardening

---

**Questions? Contact AI Team:**
- AI Service is running and ready at `http://localhost:8000`
- API docs available at `http://localhost:8000/docs`
- All endpoints tested and working

**Good luck! 🚀**
