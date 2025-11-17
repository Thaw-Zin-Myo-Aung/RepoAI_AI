// src/main/java/th/ac/mfu/repoai/repository/ConversationRepository.java
package th.ac.mfu.repoai.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import th.ac.mfu.repoai.domain.Conversation;
import th.ac.mfu.repoai.domain.ConversationStatus;

public interface ConversationRepository extends JpaRepository<Conversation, Long> {

    // List all for a GitHub user
    List<Conversation> findByUserGithubIdOrderByUpdatedAtDesc(Long githubId);

    // Filter by repo
    List<Conversation> findByUserGithubIdAndRepositoryRepoIdOrderByUpdatedAtDesc(Long githubId, Long repoId);

    // Filter by status
    List<Conversation> findByUserGithubIdAndStatusOrderByUpdatedAtDesc(Long githubId, ConversationStatus status);

    // Filter by repo + status
    List<Conversation> findByUserGithubIdAndRepositoryRepoIdAndStatusOrderByUpdatedAtDesc(
            Long githubId, Long repoId, ConversationStatus status);

    // ===== ownership & single-row =====
    Optional<Conversation> findByIdAndUserGithubId(Long id, Long githubId);

    // Latest conversation under a repo (handy for “resume last”)
    Optional<Conversation> findTop1ByUserGithubIdAndRepositoryRepoIdOrderByUpdatedAtDesc(Long githubId, Long repoId);

}
