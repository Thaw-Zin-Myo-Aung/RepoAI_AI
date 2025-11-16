package th.ac.mfu.repoai.domain;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

@Entity
public class User {
    @Id // <-- YOU NEED THIS!!!
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private Long githubId;
    private String username;
    private String email;
    private String avatarUrl;
    private String profileUrl;

    public User() {
    }

    public User(Long githubId, String username, String email, String avatarUrl, String profileUrl) {
        this.githubId = githubId;
        this.username = username;
        this.email = email;
        this.avatarUrl = avatarUrl;
        this.profileUrl = profileUrl;
    }

    public Long getGithubId() {
        return githubId;
    }

    public void setGithubId(Long githubId) {
        this.githubId = githubId;
    }

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getEmail() {
        return email;
    }

    public void setEmail(String email) {
        this.email = email;
    }

    public String getAvatarUrl() {
        return avatarUrl;
    }

    public void setAvatarUrl(String avatarUrl) {
        this.avatarUrl = avatarUrl;
    }

    public String getProfileUrl() {
        return profileUrl;
    }

    public void setProfileUrl(String profileUrl) {
        this.profileUrl = profileUrl;
    }
}
