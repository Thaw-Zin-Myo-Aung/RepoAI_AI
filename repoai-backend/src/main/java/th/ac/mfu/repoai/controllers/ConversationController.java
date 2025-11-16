// src/main/java/th/ac/mfu/repoai/controllers/ConversationController.java
package th.ac.mfu.repoai.controllers;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import io.swagger.v3.oas.annotations.Operation;

import th.ac.mfu.repoai.domain.Conversation;
import th.ac.mfu.repoai.domain.ConversationStatus;
import th.ac.mfu.repoai.repository.ConversationRepository;
import th.ac.mfu.repoai.repository.UserRepository;
import th.ac.mfu.repoai.services.ConversationService;

@RestController
@RequestMapping("/api/conversations")
public class ConversationController {

    private final ConversationService service;
    private final ConversationRepository convos;
    @SuppressWarnings("unused")
    private final UserRepository users;

    public ConversationController(
            ConversationService service,
            ConversationRepository convos,
            UserRepository users) {
        this.service = service;
        this.convos = convos;
        this.users = users;
    }

    // -----------------------------------------
    // 1) Create a conversation
    // -----------------------------------------
    @Operation(summary = "Create a conversation for a repo")
    @PostMapping
    public ResponseEntity<ConversationDTO> create(
            Authentication auth,
            @Valid @RequestBody CreateConversationRequest req) {

        Long githubId = resolveGithubId(auth, req.githubId());
        Conversation saved = service.create(
                githubId,
                req.repoId(),
                req.branchId(),
                req.title(),
                req.goal(),
                req.metadataJson());

        return ResponseEntity.ok(ConversationDTO.from(saved));
    }

    // -----------------------------------------
    // 2) List my conversations (optionally filter by repo or status)
    // -----------------------------------------
    @Operation(summary = "List the conversations")
    @GetMapping
    public ResponseEntity<List<ConversationDTO>> listMine(
            Authentication auth,
            @RequestParam(required = false) Long githubId,
            @RequestParam(required = false) Long repoId,
            @RequestParam(required = false) ConversationStatus status) {

        Long currentGithubId = resolveGithubId(auth, githubId);

        List<Conversation> list;
        if (repoId != null && status != null) {
            list = convos.findByUserGithubIdAndRepositoryRepoIdAndStatusOrderByUpdatedAtDesc(
                    currentGithubId, repoId, status);
        } else if (repoId != null) {
            list = convos.findByUserGithubIdAndRepositoryRepoIdOrderByUpdatedAtDesc(currentGithubId, repoId);
        } else if (status != null) {
            list = convos.findByUserGithubIdAndStatusOrderByUpdatedAtDesc(currentGithubId, status);
        } else {
            list = convos.findByUserGithubIdOrderByUpdatedAtDesc(currentGithubId);
        }

        return ResponseEntity.ok(list.stream().map(ConversationDTO::from).toList());
    }

    // -----------------------------------------
    // 3) Get one conversation by id (owner-only)
    // -----------------------------------------
    @Operation(summary = "get by conversation id from Db")
    @GetMapping("/{id}")
    public ResponseEntity<ConversationDTO> getOne(
            Authentication auth,
            @PathVariable Long id,
            @RequestParam(required = false) Long githubId) {

        Long currentGithubId = resolveGithubId(auth, githubId);
        Conversation convo = convos.findById(id).orElse(null);
        if (convo == null || convo.getUser() == null ||
                !currentGithubId.equals(convo.getUser().getGithubId())) {
            return ResponseEntity.notFound().build();
        }
        return ResponseEntity.ok(ConversationDTO.from(convo));
    }

    // -----------------------------------------
    // 4) Archive (soft-delete) a conversation
    // -----------------------------------------
    @Operation(summary = "sets status=ARCHIVED; record is retained")
    @PostMapping("/{id}/archive")
    public ResponseEntity<ConversationDTO> archive(
            Authentication auth,
            @PathVariable Long id,
            @RequestParam(required = false) Long githubId) {

        Long currentGithubId = resolveGithubId(auth, githubId);
        Conversation updated = service.archive(id, currentGithubId);
        return ResponseEntity.ok(ConversationDTO.from(updated));
    }

    // -------------------------
    // PUT /api/conversations/{id}
    // -------------------------
    @PutMapping("/{id}")
    public ResponseEntity<ConversationDTO> update(
            Authentication auth,
            @PathVariable Long id,
            @Valid @RequestBody UpdateConversationRequest req) {

        Long githubId = resolveGithubId(auth, req.githubId());

        Conversation updated = service.update(
                id,
                githubId,
                req.title(),
                req.goal(),
                req.branchId(), // may be null (keep current)
                req.status(), // may be null (keep current)
                req.metadataJson()); // may be null (keep current)

        return ResponseEntity.ok(ConversationDTO.from(updated));
    }

    // ---------------------------
    // DELETE /api/conversations/{id}
    // ---------------------------
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(
            Authentication auth,
            @PathVariable Long id,
            @RequestParam(required = false) Long githubId) {

        Long currentGithubId = resolveGithubId(auth, githubId);
        Conversation convo = convos.findById(id).orElse(null);
        if (convo == null || convo.getUser() == null
                || !Objects.equals(convo.getUser().getGithubId(), currentGithubId)) {
            return ResponseEntity.notFound().build();
        }

        service.delete(id, currentGithubId);
        return ResponseEntity.noContent().build();
    }

    // ===== Helpers =====
    private Long resolveGithubId(Authentication auth, Long githubIdFromClient) {
        if (githubIdFromClient != null)
            return githubIdFromClient;
        if (auth != null && auth.getName() != null && auth.getName().matches("\\d+")) {
            return Long.parseLong(auth.getName());
        }
        throw new IllegalArgumentException(
                "Cannot resolve githubId. Provide ?githubId=... or ensure OAuth login is active.");
    }

    // ===== DTOs =====

    public record CreateConversationRequest(
            @NotNull Long repoId,
            Long branchId,
            @NotBlank String title,
            @NotBlank String goal,
            String metadataJson,
            Long githubId // optional
    ) {
    }

    public record UpdateConversationRequest(
            String title,
            String goal,
            Long branchId,
            ConversationStatus status,
            String metadataJson,
            Long githubId) {
    }

    public record ConversationDTO(
            Long id,
            Long userGithubId,
            Long repoId,
            Long branchId,
            String title,
            String goal,
            ConversationStatus status,
            String metadataJson,
            LocalDateTime createdAt,
            LocalDateTime updatedAt,
            LocalDateTime lastMessageAt) {
        public static ConversationDTO from(Conversation c) {
            return new ConversationDTO(
                    c.getId(),
                    c.getUser() != null ? c.getUser().getGithubId() : null,
                    c.getRepository() != null ? c.getRepository().getRepoId() : null,
                    c.getBranch() != null ? c.getBranch().getId() : null,
                    c.getTitle(),
                    c.getGoal(),
                    c.getStatus(),
                    c.getMetadataJson(),
                    c.getCreatedAt(),
                    c.getUpdatedAt(),
                    c.getLastMessageAt());
        }
    }
}
