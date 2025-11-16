package th.ac.mfu.repoai.domain.repositorydto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import io.swagger.v3.oas.annotations.media.Schema;
import th.ac.mfu.repoai.domain.Repository;
import th.ac.mfu.repoai.domain.User;

@Schema(name = "RepositoryEntity", description = "Repository DTO exposed via API")
@JsonIgnoreProperties(ignoreUnknown = true)
public record RepositoryDto(
        @JsonProperty("repo_id") Long repoId,
        String owner,
        @JsonProperty("private") boolean isPrivate,
        @JsonProperty("full_name") String fullName,
        @JsonProperty("html_url") String htmlUrl,
        String name,
        String description,
        @JsonProperty("default_branch") String defaultBranch,
        @JsonProperty("owner_github_id") Long ownerGithubId,
        @JsonProperty("user_github_id") Long userGithubId) {

    public static RepositoryDto fromEntity(Repository e) {
        if (e == null) return null;
        Long userGithubId = e.getUser() != null ? e.getUser().getGithubId() : null;
        return new RepositoryDto(
                e.getRepoId(),
                e.getOwner(),
                e.isPrivate(),
                e.getFullName(),
                e.getHtmlUrl(),
                e.getName(),
                e.getDescription(),
                e.getDefaultBranch(),
                e.getOwnerGithubId(),
                userGithubId);
    }

    public Repository toEntity(User user) {
        Repository e = new Repository();
        e.setRepoId(this.repoId);
        e.setOwner(this.owner);
        e.setPrivate(this.isPrivate);
        e.setFullName(this.fullName);
        e.setHtmlUrl(this.htmlUrl);
        e.setName(this.name);
        e.setDescription(this.description);
        e.setDefaultBranch(this.defaultBranch);
        e.setOwnerGithubId(this.ownerGithubId);
        e.setUser(user);
        return e;
    }
}
