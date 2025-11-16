package th.ac.mfu.repoai.domain;

import java.time.LocalDateTime;

import jakarta.persistence.*;

@Entity
@Table(
    name = "repositories",
    uniqueConstraints = {
        @UniqueConstraint(
            name = "uq_repository_full_name",
            columnNames = {"full_name"}
        )
    }
)
public class Repository {

    @Id
    private Long repoId; // GitHub repo_id — unique!

    private String owner;
    private boolean isPrivate;
    private String fullName;
    private String htmlUrl;
    private String name;
    @Column(length = 1000)
    private String description;
    private String defaultBranch;   
    private Long ownerGithubId;
    
    @Enumerated(EnumType.STRING)
    private RepositoryProvider provider; // GITHUB (enum)

    // ✅ Link to user
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    public Repository() {
    }

    public Repository(Long repoId, String owner, boolean isPrivate, String fullName,
            String htmlUrl, String name, String description,
            String defaultBranch, Long ownerGithubId, String primaryLanguage,  User user) {
        this.repoId = repoId;
        this.owner = owner;
        this.isPrivate = isPrivate;
        this.fullName = fullName;
        this.htmlUrl = htmlUrl;
        this.name = name;
        this.description = description;
        this.defaultBranch = defaultBranch;
        this.ownerGithubId = ownerGithubId;
        this.user = user;
    }

    // getters and setters
    public Long getRepoId() {
        return repoId;
    }

    public void setRepoId(Long repoId) {
        this.repoId = repoId;
    }

    public String getOwner() {
        return owner;
    }

    public void setOwner(String owner) {
        this.owner = owner;
    }

    public boolean isPrivate() {
        return isPrivate;
    }

    public void setPrivate(boolean isPrivate) {
        this.isPrivate = isPrivate;
    }

    public String getFullName() {
        return fullName;
    }

    public void setFullName(String fullName) {
        this.fullName = fullName;
    }

    public String getHtmlUrl() {
        return htmlUrl;
    }

    public void setHtmlUrl(String htmlUrl) {
        this.htmlUrl = htmlUrl;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getDefaultBranch() {
        return defaultBranch;
    }

    public void setDefaultBranch(String defaultBranch) {
        this.defaultBranch = defaultBranch;
    }

    public Long getOwnerGithubId() {
        return ownerGithubId;
    }

    public void setOwnerGithubId(Long ownerGithubId) {
        this.ownerGithubId = ownerGithubId;
    }

    public User getUser() {
        return user;
    }

    public void setUser(User user) {
        this.user = user;
    }
}

enum RepositoryProvider {
    GITHUB
}