package th.ac.mfu.repoai.services;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import static org.springframework.http.HttpStatus.NOT_FOUND;

import th.ac.mfu.repoai.domain.BranchEntity;
import th.ac.mfu.repoai.domain.BranchPushRequest;
import th.ac.mfu.repoai.domain.branchdto.BranchSummary;

import th.ac.mfu.repoai.repository.BranchRepository;
import th.ac.mfu.repoai.repository.RepositoryRepository;

import org.springframework.security.core.Authentication;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.stream.Collectors;

@Service
public class BranchSyncService {

    private final GitServices git;
    private final BranchRepository branches;
    private final RepositoryRepository repos;

    public BranchSyncService(GitServices git, BranchRepository branches, RepositoryRepository repos) {
        this.git = git;
        this.branches = branches;
        this.repos = repos;
    }

    /**
     * Pull branches from GitHub, upsert into DB, optionally purge stale ones,
     * return DB snapshot.
     */
    @Transactional
    public List<BranchEntity> syncBranches(Authentication auth, String owner, String repo) {
        var localRepo = repos.findByOwnerAndName(owner, repo)
                .orElseThrow(() -> new ResponseStatusException(
                        NOT_FOUND,
                        "No local row for %s/%s. Call /api/github/sync_repos and use exact owner+repo name."
                                .formatted(owner, repo)));

        Long repoId = localRepo.getRepoId();
        String defaultBranchName = localRepo.getDefaultBranch();

        // paginate defensively
        int page = 1, perPage = 100;
        new java.util.ArrayList<BranchSummary>(); // (only to guide autocomplete)
        java.util.ArrayList<BranchSummary> all = new java.util.ArrayList<>();
        while (true) {
            List<BranchSummary> batch = git.listBranches(auth, owner, repo, null, page, perPage);
            if (batch == null || batch.isEmpty())
                break;
            all.addAll(batch);
            if (batch.size() < perPage)
                break;
            page++;
        }

        LocalDateTime now = LocalDateTime.now();

        for (BranchSummary b : all) {
            String name = b.name();
            String sha = (b.commit() != null) ? b.commit().sha() : null;
            String url = (b.commit() != null) ? b.commit().url() : null;

            var entity = branches.findByRepoIdAndName(repoId, name).orElseGet(() -> {
                var e = new BranchEntity();
                e.setRepoId(repoId);
                e.setName(name);
                return e;
            });

            // commit_sha is NOT NULL. If sha is null (rare), keep old or set empty string
            // for new rows.
            if (sha != null) {
                entity.setCommitSha(sha);
            } else if (entity.getCommitSha() == null) {
                entity.setCommitSha(""); // or relax @Column(nullable=false)
            }

            entity.setCommitUrl(url);
            entity.setProtectedFlag(b.protectedBranch());
            entity.setDefaultFlag(Objects.equals(defaultBranchName, name));
            entity.setProtectionUrl(b.protectionUrl());
            entity.setProtectionJson(toJson(b.protection()));
            entity.setLastSyncedAt(now);

            branches.save(entity);
        }

        // remove branches that no longer exist on GitHub
        List<String> keepNames = all.stream().map(BranchSummary::name).collect(Collectors.toList());
        if (!keepNames.isEmpty()) {
            branches.deleteByRepoIdAndNameNotIn(repoId, keepNames);
        }

        return branches.findByRepoIdOrderByNameAsc(repoId);
    }

    private String toJson(Object o) {
        try {
            return o == null ? null : new com.fasterxml.jackson.databind.ObjectMapper().writeValueAsString(o);
        } catch (Exception e) {
            return null;
        }
    }

    public void createAndPushBranch(
            String token, String owner, String repo,
            String baseBranch, String newBranch,
            List<BranchPushRequest.FileChange> files, String commitMessage) {
        // 1. Get base branch SHA from GitHub
        String sha = git.getBranchSha(owner, repo, baseBranch, token);

        // 2. Create a new branch from base branch
        git.createBranch(owner, repo, newBranch, sha, token);

        // 3. Commit/push each file change
        for (BranchPushRequest.FileChange file : files) {
            git.putFile(owner, repo, file, commitMessage, newBranch, token);
        }

        // 4. Sync DB with GitHub state
        syncBranches(null, owner, repo);
    }

}