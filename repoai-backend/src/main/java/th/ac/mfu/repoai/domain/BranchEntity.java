package th.ac.mfu.repoai.domain;

import jakarta.persistence.*;
import java.time.LocalDateTime;

@Entity
@Table(
    name = "branch",
    uniqueConstraints = @UniqueConstraint(
        name = "uq_branch_repo_name",
        columnNames = {"repo_id", "name"}
    )
)
public class BranchEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // Link to your existing repository PK (repo_id)
    @Column(name = "repo_id", nullable = false)
    private Long repoId;

    @Column(nullable = false, length = 255)
    private String name;

    @Column(name = "commit_sha", nullable = false, length = 40)
    private String commitSha;

    @Column(name = "protected_flag", nullable = false)
    private boolean protectedFlag;

    @Column(name = "default_flag", nullable = false)
    private boolean defaultFlag;

    @Column(name = "commit_url", length = 1000)
    private String commitUrl;

    @Column(name = "protection_url", length = 1000)
    private String protectionUrl;

    // For MySQL JSON type (okay to keep as TEXT on other DBs)
    @Column(name = "protection_json", columnDefinition = "json")
    private String protectionJson;

    @Column(name = "last_synced_at", nullable = false)
    private LocalDateTime lastSyncedAt;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @PrePersist
    void onCreate() {
        var now = LocalDateTime.now();
        createdAt = now;
        updatedAt = now;
        if (lastSyncedAt == null) lastSyncedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    // -- getters/setters --

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public Long getRepoId() { return repoId; }
    public void setRepoId(Long repoId) { this.repoId = repoId; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getCommitSha() { return commitSha; }
    public void setCommitSha(String commitSha) { this.commitSha = commitSha; }

    public boolean isProtectedFlag() { return protectedFlag; }
    public void setProtectedFlag(boolean protectedFlag) { this.protectedFlag = protectedFlag; }

    public boolean isDefaultFlag() { return defaultFlag; }
    public void setDefaultFlag(boolean defaultFlag) { this.defaultFlag = defaultFlag; }

    public String getCommitUrl() { return commitUrl; }
    public void setCommitUrl(String commitUrl) { this.commitUrl = commitUrl; }

    public String getProtectionUrl() { return protectionUrl; }
    public void setProtectionUrl(String protectionUrl) { this.protectionUrl = protectionUrl; }

    public String getProtectionJson() { return protectionJson; }
    public void setProtectionJson(String protectionJson) { this.protectionJson = protectionJson; }

    public LocalDateTime getLastSyncedAt() { return lastSyncedAt; }
    public void setLastSyncedAt(LocalDateTime lastSyncedAt) { this.lastSyncedAt = lastSyncedAt; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }

    public LocalDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(LocalDateTime updatedAt) { this.updatedAt = updatedAt; }
}
