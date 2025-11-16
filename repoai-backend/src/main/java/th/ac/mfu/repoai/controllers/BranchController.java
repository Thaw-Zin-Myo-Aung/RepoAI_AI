package th.ac.mfu.repoai.controllers;

import io.swagger.v3.oas.annotations.Operation;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import th.ac.mfu.repoai.domain.BranchEntity;
import th.ac.mfu.repoai.domain.BranchPushRequest;
import th.ac.mfu.repoai.repository.BranchRepository;
import th.ac.mfu.repoai.repository.RepositoryRepository;
import th.ac.mfu.repoai.services.BranchSyncService;

import java.util.List;

@RestController
@RequestMapping("/api")
public class BranchController {

    private final BranchSyncService syncService;
    private final BranchRepository branchRepo;
    private final RepositoryRepository repoRepo;

    public BranchController(BranchSyncService syncService, BranchRepository branchRepo, RepositoryRepository repoRepo) {
        this.syncService = syncService;
        this.branchRepo = branchRepo;
        this.repoRepo = repoRepo;
    }

    // A) Read branches from DB by our repository PK (repo_id)
    @Operation(summary = "List branches from DB")
    @GetMapping("/repos/{repoId}/branches")
    public List<BranchEntity> listFromDb(@PathVariable Long repoId) {
        return branchRepo.findByRepoIdOrderByNameAsc(repoId);
    }

    // B) Get one branch (DB)
    @Operation(summary = "Get a single branch from DB")
    @GetMapping("/repos/{repoId}/branches/{branchName}")
    public BranchEntity getFromDb(@PathVariable Long repoId, @PathVariable String branchName) {
        return branchRepo.findByRepoIdAndName(repoId, branchName)
                .orElseThrow(() -> new IllegalArgumentException("Branch not found"));
    }

    // C) Sync from GitHub into DB, then return the snapshot
    @Operation(summary = "Sync branches from GitHub into DB and return the snapshot")
    @PostMapping("/github/{owner}/{repo}/branches/sync")
    public List<BranchEntity> syncAndList(Authentication auth,
            @PathVariable String owner,
            @PathVariable String repo) {
        return syncService.syncBranches(auth, owner, repo);
    }

    @Operation(summary = "Create a new branch on GitHub and push refactored code")
    @PostMapping("/github/{owner}/{repo}/branches/create-push")
    public ResponseEntity<String> createAndPushBranch(
            @RequestHeader("Authorization") String authHeader,
            @PathVariable String owner,
            @PathVariable String repo,
            @RequestBody BranchPushRequest req) {
        String token = authHeader.replace("Bearer ", "").trim();
        syncService.createAndPushBranch(token, req.owner, req.repo, req.baseBranch, req.newBranch, req.fileChanges,
                req.commitMessage);
        return ResponseEntity.ok("Branch created and code pushed.");
    }

}