package th.ac.mfu.repoai.controllers;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.ArraySchema;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponse;

import th.ac.mfu.repoai.domain.User;
import th.ac.mfu.repoai.domain.Repository;
import th.ac.mfu.repoai.domain.repositorydto.ContextChunk;
import th.ac.mfu.repoai.domain.repositorydto.RepositoryDto;
import th.ac.mfu.repoai.repository.ContextChunkRepository;
import th.ac.mfu.repoai.repository.RepositoryRepository;
import th.ac.mfu.repoai.repository.UserRepository;
import th.ac.mfu.repoai.services.GitServices;
import th.ac.mfu.repoai.services.RepositoryIndexingService;

@RestController
@RequestMapping("/api/repos")
public class RepositoryController {
    private final UserRepository userRepository;
    private final RepositoryRepository repositoryRepository;
    private final GitServices gitServices;
     private final RepositoryIndexingService indexingService;
     private final ContextChunkRepository contextChunkRepository;

    public RepositoryController(UserRepository userRepository,
            RepositoryRepository repositoryRepository,
            GitServices gitServices, RepositoryIndexingService indexingService,
            ContextChunkRepository contextChunkRepository) {
        this.userRepository = userRepository;
        this.repositoryRepository = repositoryRepository;
        this.gitServices = gitServices;
         this.indexingService = indexingService; 
         this.contextChunkRepository = contextChunkRepository;
    }

    // List repositories saved for a user (by user's GitHub ID)
    @Operation(summary = "List repositories for a GitHub user (from DB)",
            responses = {
                @ApiResponse(responseCode = "200", description = "OK",
                    content = @Content(array = @ArraySchema(schema = @Schema(implementation = RepositoryDto.class))))
            })
    @GetMapping("/")
    public ResponseEntity<List<RepositoryDto>> getRepos(@RequestParam long githubId) {
        User user = userRepository.findByGithubId(githubId)
                .orElseThrow(() -> new RuntimeException("User not found"));
        List<Repository> repos = repositoryRepository.findByUser(user);
        List<RepositoryDto> dto = repos.stream().map(RepositoryDto::fromEntity).toList();
        return ResponseEntity.ok(dto);
    }

    // (Removed) DB-only create/update/delete endpoints have been replaced by GitHub-backed endpoints below.

    // =========================
    // GitHub-backed operations
    // =========================

    @Operation(summary = "Create repo on GitHub and sync to DB",
            responses = {
                @ApiResponse(responseCode = "201", description = "Created",
                    content = @Content(schema = @Schema(implementation = RepositoryDto.class)))
            })
    @PostMapping("/")
    public ResponseEntity<RepositoryDto> createRepos(@RequestBody Map<String, Object> payload) {
        String name = (String) payload.get("name");
        String description = (String) payload.get("description");
        Boolean isPrivate = (Boolean) payload.get("private");
        String defaultBranch = (String) payload.get("default_branch");
        Boolean autoInit = (Boolean) payload.get("auto_init");
        return gitServices.createUserRepositoryAndSave(name, description, isPrivate, defaultBranch, autoInit);
    }

    @Operation(summary = "Update repo on GitHub and sync to DB",
            responses = {
                @ApiResponse(responseCode = "200", description = "OK",
                    content = @Content(schema = @Schema(implementation = RepositoryDto.class)))
            })
    @PutMapping("/{owner}/{repo}")
    public ResponseEntity<RepositoryDto> updateRepos(@PathVariable String owner,
            @PathVariable String repo,
            @RequestBody Map<String, Object> updates) {
        // Guard: GitHub expects repo NAME here, not numeric repo_id
        if (repo != null && repo.matches("\\d+")) {
            return ResponseEntity.badRequest().build();
        }
        return gitServices.updateRepositoryAndSave(owner, repo, updates);
    }

    @Operation(summary = "Delete repo on GitHub and remove from DB",
            responses = {
                @ApiResponse(responseCode = "204", description = "No Content")
            })
    @DeleteMapping("/{owner}/{repo}")
    public ResponseEntity<Void> deleteRepos(@PathVariable String owner, @PathVariable String repo) {
        // Guard: GitHub expects repo NAME here, not numeric repo_id
        if (repo != null && repo.matches("\\d+")) {
            return ResponseEntity.badRequest().build();
        }
        return gitServices.deleteRepositoryAndRemove(owner, repo);
    }
 
    @PostMapping("/connect")
@Operation(summary = "Connect repository and trigger indexing")
public ResponseEntity<Map<String, Object>> connectRepository(
        @RequestBody Map<String, Object> payload) {
    
    try {
        Long githubId = ((Number) payload.get("githubId")).longValue();
        Long repoId = ((Number) payload.get("repoId")).longValue();
        
        User user = userRepository.findByGithubId(githubId)
                .orElseThrow(() -> new RuntimeException("User not found"));
        
        // Start indexing process
        Repository connectedRepo = indexingService.connectAndIndexRepository(
            user, repoId
        );
        
        // Fetch the stored chunks to show in response
        List<ContextChunk> chunks = contextChunkRepository.findByRepoId(repoId);
        
        // Convert chunks to readable format - FIXED
        List<Map<String, Object>> chunkDetails = chunks.stream()
            .map(chunk -> {
                Map<String, Object> chunkMap = new HashMap<>();
                chunkMap.put("chunk_id", chunk.getChunkId());
                chunkMap.put("path", chunk.getPath());
                chunkMap.put("start_line", chunk.getStartLine());
                chunkMap.put("end_line", chunk.getEndLine());
                chunkMap.put("symbol_fqn", chunk.getSymbolFqn() != null ? chunk.getSymbolFqn() : "");
                chunkMap.put("symbol_kind", chunk.getSymbolKind().toString());
                chunkMap.put("content_hash", chunk.getContentHash());
                chunkMap.put("qdrant_vector_id", chunk.getQdrantVectorId() != null ? chunk.getQdrantVectorId() : "NOT_SET");
                chunkMap.put("embedding_model", chunk.getEmbeddingModel() != null ? chunk.getEmbeddingModel() : "NOT_SET");
                chunkMap.put("embedding_dim", chunk.getEmbeddingDim() != null ? chunk.getEmbeddingDim() : 0);
                return chunkMap;
            })
            .collect(Collectors.toList());
        
        // Return response - FIXED
        Map<String, Object> response = new HashMap<>();
        response.put("status", "success");
        response.put("message", "Repository connected and indexed successfully");
        response.put("repo_id", connectedRepo.getRepoId());
        response.put("repo_name", connectedRepo.getFullName());
        response.put("chunks_created", chunks.size());
        response.put("chunks", chunkDetails);
        
        return ResponseEntity.ok(response);
        
    } catch (Exception e) {
        Map<String, Object> errorResponse = new HashMap<>();
        errorResponse.put("status", "error");
        errorResponse.put("message", e.getMessage());
        
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(errorResponse);
    }
}


}
