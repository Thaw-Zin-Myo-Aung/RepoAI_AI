package th.ac.mfu.repoai.controllers;

import java.time.LocalDateTime;
import java.util.List;

import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import io.swagger.v3.oas.annotations.Operation;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;

import th.ac.mfu.repoai.domain.Chat;
import th.ac.mfu.repoai.services.ChatService;

@RestController
@RequestMapping("/api/conversations/{convoId}/chats")
public class ChatController {

    private final ChatService service;

    public ChatController(ChatService service) {
        this.service = service;
    }

    // GET list messages for a conversation
    @Operation(summary = "List chat messages for a conversation (ascending by time)")
    @GetMapping
    public ResponseEntity<List<ChatDTO>> list(
            Authentication auth,
            @PathVariable Long convoId,
            @RequestParam(required = false) Long githubId) {
        Long gid = resolveGithubId(auth, githubId);
        List<Chat> list = service.list(convoId, gid);
        return ResponseEntity.ok(list.stream().map(ChatDTO::from).toList());
    }

    // POST create message
    @Operation(summary = "Create a chat message in the conversation")
    @PostMapping
    public ResponseEntity<ChatDTO> create(
            Authentication auth,
            @PathVariable Long convoId,
            @Valid @RequestBody CreateChatRequest req) {
        Long gid = resolveGithubId(auth, req.githubId());
        Chat saved = service.create(convoId, gid, req.content(), req.metadataJson());
        return ResponseEntity.ok(ChatDTO.from(saved));
    }

    // PUT update message
    @Operation(summary = "Update a chat message (content/metadata)")
    @PutMapping("/{chatId}")
    public ResponseEntity<ChatDTO> update(
            Authentication auth,
            @PathVariable Long convoId,
            @PathVariable Long chatId,
            @Valid @RequestBody UpdateChatRequest req) {
        Long gid = resolveGithubId(auth, req.githubId());
        Chat updated = service.update(convoId, chatId, gid, req.content(), req.metadataJson());
        return ResponseEntity.ok(ChatDTO.from(updated));
    }

    // DELETE remove message
    @Operation(summary = "Delete a chat message")
    @DeleteMapping("/{chatId}")
    public ResponseEntity<Void> delete(
            Authentication auth,
            @PathVariable Long convoId,
            @PathVariable Long chatId,
            @RequestParam(required = false) Long githubId) {
        Long gid = resolveGithubId(auth, githubId);
        service.delete(convoId, chatId, gid);
        return ResponseEntity.noContent().build();
    }

    private Long resolveGithubId(Authentication auth, Long githubIdFromClient) {
        if (githubIdFromClient != null)
            return githubIdFromClient;
        if (auth != null && auth.getName() != null && auth.getName().matches("\\d+")) {
            return Long.parseLong(auth.getName());
        }
        throw new IllegalArgumentException(
                "Cannot resolve githubId. Provide ?githubId=... or ensure OAuth login is active.");
    }

    // DTOs
    public record CreateChatRequest(
            @NotBlank String content,
            String metadataJson,
            Long githubId) {
    }

    public record UpdateChatRequest(
            String content,
            String metadataJson,
            Long githubId) {
    }

    public record ChatDTO(
            Long id,
            Long conversationId,
            String content,
            String metadataJson,
            LocalDateTime createdAt,
            LocalDateTime updatedAt) {
        public static ChatDTO from(Chat c) {
            return new ChatDTO(
                    c.getId(),
                    c.getConversation() != null ? c.getConversation().getId() : null,
                    c.getContent(),
                    c.getMetadataJson(),
                    c.getCreatedAt(),
                    c.getUpdatedAt());
        }
    }
}
