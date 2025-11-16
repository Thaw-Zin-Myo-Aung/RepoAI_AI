package th.ac.mfu.repoai.domain.repositorydto;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(name = "context_chunks",
    indexes = {
        @Index(name = "idx_repo_path", columnList = "repo_id,path"),
        @Index(name = "idx_repo_symbol", columnList = "repo_id,symbol_fqn")
    }
)
public class ContextChunk {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long chunkId;
    
    @Column(name = "repo_id", nullable = false)
    private Long repoId;
    
    @Column(nullable = false, length = 1024)
    private String path; // e.g., "src/main/java/UserService.java"
    
    @Column(nullable = false)
    private Integer startLine;
    
    @Column(nullable = false)
    private Integer endLine;
    
    @Column(nullable = false, length = 40)
    private String commitSha; // Git commit hash
    
    @Column(length = 512)
    private String symbolFqn; // e.g., "com.example.UserService.createUser"
    
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private SymbolKind symbolKind;
    
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private SourceType sourceType;
    
    @Column(nullable = false, length = 40)
    private String contentHash; // SHA-256 for change detection
    
    @Column(length = 255)
    private String qdrantVectorId; // UUID linking to Qdrant
    
    @Column(length = 128)
    private String embeddingModel; // e.g., "BAAI/bge-small-en-v1.5"
    
    private Integer embeddingDim; // 384 or 768
    
    @Column(nullable = false)
    private LocalDateTime createdAt;
    
    private LocalDateTime lastBuiltAt;
    
    // Constructors
    public ContextChunk() {
        this.createdAt = LocalDateTime.now();
        this.sourceType = SourceType.CODE;
        this.symbolKind = SymbolKind.UNKNOWN;
    }
    
    // Getters and Setters
    public Long getChunkId() { return chunkId; }
    public void setChunkId(Long chunkId) { this.chunkId = chunkId; }
    
    public Long getRepoId() { return repoId; }
    public void setRepoId(Long repoId) { this.repoId = repoId; }
    
    public String getPath() { return path; }
    public void setPath(String path) { this.path = path; }
    
    public Integer getStartLine() { return startLine; }
    public void setStartLine(Integer startLine) { this.startLine = startLine; }
    
    public Integer getEndLine() { return endLine; }
    public void setEndLine(Integer endLine) { this.endLine = endLine; }
    
    public String getCommitSha() { return commitSha; }
    public void setCommitSha(String commitSha) { this.commitSha = commitSha; }
    
    public String getSymbolFqn() { return symbolFqn; }
    public void setSymbolFqn(String symbolFqn) { this.symbolFqn = symbolFqn; }
    
    public SymbolKind getSymbolKind() { return symbolKind; }
    public void setSymbolKind(SymbolKind symbolKind) { this.symbolKind = symbolKind; }
    
    public SourceType getSourceType() { return sourceType; }
    public void setSourceType(SourceType sourceType) { this.sourceType = sourceType; }
    
    public String getContentHash() { return contentHash; }
    public void setContentHash(String contentHash) { this.contentHash = contentHash; }
    
    public String getQdrantVectorId() { return qdrantVectorId; }
    public void setQdrantVectorId(String qdrantVectorId) { this.qdrantVectorId = qdrantVectorId; }
    
    public String getEmbeddingModel() { return embeddingModel; }
    public void setEmbeddingModel(String embeddingModel) { this.embeddingModel = embeddingModel; }
    
    public Integer getEmbeddingDim() { return embeddingDim; }
    public void setEmbeddingDim(Integer embeddingDim) { this.embeddingDim = embeddingDim; }
    
    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
    
    public LocalDateTime getLastBuiltAt() { return lastBuiltAt; }
    public void setLastBuiltAt(LocalDateTime lastBuiltAt) { this.lastBuiltAt = lastBuiltAt; }
}




