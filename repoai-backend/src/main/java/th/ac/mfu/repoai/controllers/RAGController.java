package th.ac.mfu.repoai.controllers;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;
import th.ac.mfu.repoai.domain.repositorydto.ContextChunk;
import th.ac.mfu.repoai.repository.ContextChunkRepository;

import java.util.*;
import java.util.stream.Collectors;

@RestController
@RequestMapping("/api/rag")
public class RAGController {
    
    @Autowired
    private RestTemplate restTemplate;
    
    @Autowired
    private ContextChunkRepository contextChunkRepository;
    
    @Value("${ai.service.url:http://localhost:5000}")
    private String aiServiceUrl;
    
    /**
     * Search for relevant code chunks using RAG
     */
    @PostMapping("/search")
    public ResponseEntity<Map<String, Object>> searchContext(
            @RequestBody Map<String, Object> payload) {
        
        try {
            Long repoId = ((Number) payload.get("repoId")).longValue();
            String query = (String) payload.get("query");
            Integer topK = (Integer) payload.getOrDefault("topK", 10);
            
            // Step 1: Convert query to embedding
            HttpEntity<Map<String, Object>> embeddingRequest = new HttpEntity<>(
                Map.of("query", query)
            );
            
            ResponseEntity<Map> embeddingResponse = restTemplate.postForEntity(
                aiServiceUrl + "/embeddings/encode",
                embeddingRequest,
                Map.class
            );
            
            if (!embeddingResponse.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("Failed to encode query");
            }
            
            List<Double> queryVector = 
                (List<Double>) embeddingResponse.getBody().get("embedding");
            
            // Step 2: Search Qdrant
            HttpEntity<Map<String, Object>> searchRequest = new HttpEntity<>(
                Map.of(
                    "collection", "code_chunks",
                    "vector", queryVector,
                    "limit", topK,
                    "filter", Map.of("repo_id", repoId)
                )
            );
            
            ResponseEntity<Map> searchResponse = restTemplate.postForEntity(
                aiServiceUrl + "/qdrant/search",
                searchRequest,
                Map.class
            );
            
            if (!searchResponse.getStatusCode().is2xxSuccessful()) {
                throw new RuntimeException("Qdrant search failed");
            }
            
            List<Map<String, Object>> qdrantResults = 
                (List<Map<String, Object>>) searchResponse.getBody().get("results");
            
            // Step 3: Enrich with MySQL metadata
            List<Long> chunkIds = qdrantResults.stream()
                .map(r -> ((Number) r.get("chunk_id")).longValue())
                .collect(Collectors.toList());
            
            List<ContextChunk> chunks = contextChunkRepository.findByChunkIdIn(chunkIds);
            
            // Step 4: Combine results
            List<Map<String, Object>> enrichedResults = new ArrayList<>();
            for (Map<String, Object> qdrantResult : qdrantResults) {
                Long chunkId = ((Number) qdrantResult.get("chunk_id")).longValue();
                Double score = (Double) qdrantResult.get("score");
                
                ContextChunk chunk = chunks.stream()
                    .filter(c -> c.getChunkId().equals(chunkId))
                    .findFirst()
                    .orElse(null);
                
                if (chunk != null) {
                    enrichedResults.add(Map.of(
                        "chunk_id", chunkId,
                        "score", score,
                        "path", chunk.getPath(),
                        "start_line", chunk.getStartLine(),
                        "end_line", chunk.getEndLine(),
                        "symbol_fqn", chunk.getSymbolFqn() != null ? chunk.getSymbolFqn() : "",
                        "symbol_kind", chunk.getSymbolKind().toString()
                    ));
                }
            }
            
            return ResponseEntity.ok(Map.of(
                "status", "success",
                "query", query,
                "count", enrichedResults.size(),
                "results", enrichedResults
            ));
            
        } catch (Exception e) {
            return ResponseEntity.status(500).body(Map.of(
                "status", "error",
                "message", e.getMessage()
            ));
        }
    }
}
