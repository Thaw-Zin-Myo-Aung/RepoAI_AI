package th.ac.mfu.repoai.services;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;
import java.util.Objects;

import th.ac.mfu.repoai.domain.*;
import th.ac.mfu.repoai.repository.*;

@Service
public class ConversationService {

    private final ConversationRepository convos;
    private final UserRepository users;
    private final RepositoryRepository repos;
    private final BranchRepository branches;

    public ConversationService(
            ConversationRepository convos,
            UserRepository users,
            RepositoryRepository repos,
            BranchRepository branches) {
        this.convos = convos;
        this.users = users;
        this.repos = repos;
        this.branches = branches;
    }

    @Transactional
    public Conversation create(
            Long githubId, Long repoId, Long branchIdOrNull,
            String title, String goal, String metadataJson) {

        var user = users.findByGithubId(githubId)
                .orElseThrow(() -> new IllegalArgumentException("User (githubId=" + githubId + ") not found"));

        var repo = repos.findById(repoId)
                .orElseThrow(() -> new IllegalArgumentException("Repository not found"));

        BranchEntity branch = null;
        if (branchIdOrNull != null) {
            branch = branches.findById(branchIdOrNull)
                    .orElseThrow(() -> new IllegalArgumentException("Branch not found"));
            if (!Objects.equals(branch.getRepoId(), repo.getRepoId())) {
                throw new IllegalArgumentException("Branch does not belong to repository");
            }
        }

        var c = new Conversation();
        c.setUser(user);
        c.setRepository(repo);
        c.setBranch(branch);
        c.setTitle(title);
        c.setGoal(goal);
        c.setMetadataJson(metadataJson);

        return convos.save(c);
    }

    @Transactional(readOnly = true)
    public List<Conversation> listMine(Long githubId) {
        return convos.findByUserGithubIdOrderByUpdatedAtDesc(githubId);
    }

    @Transactional
    public Conversation archive(Long convoId, Long githubId) {
        var c = convos.findById(convoId)
                .orElseThrow(() -> new IllegalArgumentException("Conversation not found"));

        // Ownership check via GitHub id
        if (c.getUser() == null || !Objects.equals(c.getUser().getGithubId(), githubId)) {
            throw new SecurityException("Not your conversation");
        }

        c.setStatus(ConversationStatus.ARCHIVED);
        return c;
    }

    @Transactional
    public Conversation update(
            Long convoId,
            Long githubId,
            String title,
            String goal,
            Long branchIdOrNull,
            ConversationStatus status,
            String metadataJson) {

        var c = convos.findById(convoId)
                .orElseThrow(() -> new IllegalArgumentException("Conversation not found"));

        if (c.getUser() == null || !Objects.equals(c.getUser().getGithubId(), githubId)) {
            throw new SecurityException("Not your conversation");
        }

        if (title != null && !title.isBlank())
            c.setTitle(title);
        if (goal != null && !goal.isBlank())
            c.setGoal(goal);
        if (status != null)
            c.setStatus(status);
        if (metadataJson != null)
            c.setMetadataJson(metadataJson);

        if (branchIdOrNull != null) {
            // set/replace branch (or validate)
            var branch = branches.findById(branchIdOrNull)
                    .orElseThrow(() -> new IllegalArgumentException("Branch not found"));
            if (!Objects.equals(branch.getRepoId(), c.getRepository().getRepoId())) {
                throw new IllegalArgumentException("Branch does not belong to conversation's repository");
            }
            c.setBranch(branch);
        }

        return c;
    }

    @Transactional
    public void delete(Long convoId, Long githubId) {
        var c = convos.findById(convoId)
                .orElseThrow(() -> new IllegalArgumentException("Conversation not found"));
        if (c.getUser() == null || !Objects.equals(c.getUser().getGithubId(), githubId)) {
            throw new SecurityException("Not your conversation");
        }
        convos.delete(c);
    }
}
