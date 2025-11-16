package th.ac.mfu.repoai.services;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import th.ac.mfu.repoai.domain.repositorydto.ContextChunk;
import th.ac.mfu.repoai.domain.repositorydto.SymbolKind;
import th.ac.mfu.repoai.domain.Repository;
import th.ac.mfu.repoai.domain.User;
import th.ac.mfu.repoai.repository.ContextChunkRepository;
import th.ac.mfu.repoai.repository.RepositoryRepository;

import java.time.LocalDateTime;
import java.util.*;
import java.util.stream.Collectors;

@Service
public class RepositoryIndexingService {
    
    @Autowired
    private RepositoryRepository repositoryRepository;
    
    @Autowired
    private ContextChunkRepository contextChunkRepository;
    
    @Autowired
    private RestTemplate restTemplate;
    
    @Value("${ai.service.url:http://localhost:5000}")
    private String aiServiceUrl;
    
    /**
     * Main method: Connect repository and trigger 3-phase indexing
     */
    public Repository connectAndIndexRepository(User user, Long repoId) {
        // Get repository from database (sync_repos should have saved it already)
        Repository repo = repositoryRepository.findById(repoId)
            .orElseThrow(() -> new RuntimeException("Repository not found. Please run sync_repos first."));
        
        // Link to user
        repo.setUser(user);
        repositoryRepository.save(repo);
        
        // Phase 2: Parse and chunk repository
        List<ContextChunk> chunks = parseAndChunkRepository(repo);
        
        // Phase 3: Generate embeddings and store in Qdrant
        storeEmbeddings(chunks);
        
        return repo;
    }
    
    /**
     * Phase 2: Call AI Service to parse repository and create chunks
     */
    private List<ContextChunk> parseAndChunkRepository(Repository repo) {
        Map<String, Object> payload = Map.of(
            "repo_id", repo.getRepoId(),
            "owner", repo.getOwner(),
            "name", repo.getName(),
            "default_branch", repo.getDefaultBranch()
        );
        
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload);
        
        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(
                aiServiceUrl + "/indexing/parse",
                request,
                Map.class
            );
            
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("AI Service parsing failed");
            }
            
            Map<String, Object> body = response.getBody();
            List<Map<String, Object>> chunkData = 
                (List<Map<String, Object>>) body.get("chunks");
            
            // Convert to ContextChunk entities
            List<ContextChunk> chunks = chunkData.stream()
                .map(data -> {
                    ContextChunk chunk = new ContextChunk();
                    chunk.setRepoId(repo.getRepoId());
                    chunk.setPath((String) data.get("path"));
                    chunk.setStartLine((Integer) data.get("start_line"));   
                    chunk.setEndLine((Integer) data.get("end_line"));
                    chunk.setSymbolFqn((String) data.get("symbol_fqn"));
                    chunk.setSymbolKind(
                        SymbolKind.valueOf((String) data.get("symbol_kind"))
                    );
                    chunk.setContentHash((String) data.get("content_hash"));
                    chunk.setCommitSha(repo.getDefaultBranch());
                    return chunk;
                })
                .collect(Collectors.toList());
            
            // Save chunks to MySQL
            return contextChunkRepository.saveAll(chunks);
            
        } catch (Exception e) {
            throw new RuntimeException("Failed to parse repository: " + e.getMessage(), e);
        }
    }
    
    /**
     * Phase 3: Generate embeddings and store in Qdrant
     */
    private void storeEmbeddings(List<ContextChunk> chunks) {
        // Prepare chunk payloads
        List<Map<String, Object>> chunkPayloads = chunks.stream()
            .map(chunk -> Map.of(
                "chunk_id", chunk.getChunkId(),
                "content", getChunkContent(chunk),
                "metadata", Map.of(
                    "repo_id", chunk.getRepoId(),
                    "path", chunk.getPath(),
                    "symbol_fqn", chunk.getSymbolFqn() != null ? chunk.getSymbolFqn() : "",
                    "start_line", chunk.getStartLine(),
                    "end_line", chunk.getEndLine()
                )
            ))
            .collect(Collectors.toList());
        
        Map<String, Object> payload = Map.of("chunks", chunkPayloads);
        HttpEntity<Map<String, Object>> request = new HttpEntity<>(payload);
        
        try {
            ResponseEntity<Map> response = restTemplate.postForEntity(
                aiServiceUrl + "/embeddings/store",
                request,
                Map.class
            );
            
            if (!response.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("Embedding storage failed");
            }
            
            Map<String, Object> body = response.getBody();
            List<Map<String, Object>> vectorIds = 
                (List<Map<String, Object>>) body.get("vector_ids");
            
            // Update chunks with Qdrant vector IDs
            for (Map<String, Object> vectorData : vectorIds) {
                Long chunkId = ((Number) vectorData.get("chunk_id")).longValue();
                String qdrantId = (String) vectorData.get("qdrant_id");
                String embeddingModel = (String) vectorData.get("embedding_model");
                Integer embeddingDim = (Integer) vectorData.get("embedding_dim");
                
                chunks.stream()
                    .filter(c -> c.getChunkId().equals(chunkId))
                    .findFirst()
                    .ifPresent(chunk -> {
                        chunk.setQdrantVectorId(qdrantId);
                        chunk.setEmbeddingModel(embeddingModel);
                        chunk.setEmbeddingDim(embeddingDim);
                        chunk.setLastBuiltAt(LocalDateTime.now());
                    });
            }
            
            // Save updated chunks
            contextChunkRepository.saveAll(chunks);
            
        } catch (Exception e) {
            throw new RuntimeException("Failed to generate embeddings: " + e.getMessage(), e);
        }
    }
    
    /**
     * Helper: Get code content for a chunk
     * For MVP, returns placeholder. In production, fetch from GitHub API
     */
    private String getChunkContent(ContextChunk chunk) {
        // TODO: Implement actual code fetching from GitHub
        return String.format("// Code from %s (lines %d-%d)", 
            chunk.getPath(), chunk.getStartLine(), chunk.getEndLine());
    }
}
