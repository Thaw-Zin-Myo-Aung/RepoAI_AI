package th.ac.mfu.repoai.services;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import th.ac.mfu.repoai.domain.Chat;
import th.ac.mfu.repoai.domain.Conversation;
import th.ac.mfu.repoai.repository.ChatRepository;
import th.ac.mfu.repoai.repository.ConversationRepository;

@Service
public class ChatService {

    private final ChatRepository chats;
    private final ConversationRepository convos;

    public ChatService(ChatRepository chats, ConversationRepository convos) {
        this.chats = chats;
        this.convos = convos;
    }

    @Transactional(readOnly = true)
    public List<Chat> list(Long convoId, Long githubId) {
        Conversation c = requireOwnedConversation(convoId, githubId);
        // c validated; just list by id
        return chats.findByConversation_IdOrderByCreatedAtAsc(c.getId());
    }

    @Transactional
    public Chat create(Long convoId, Long githubId, String content, String metadataJson) {
        Conversation c = requireOwnedConversation(convoId, githubId);

        Chat m = new Chat();
        m.setConversation(c);
        m.setContent(content);
        m.setMetadataJson(metadataJson);

        Chat saved = chats.save(m);

        // bump lastMessageAt on conversation
        c.setLastMessageAt(LocalDateTime.now());

        return saved;
    }

    @Transactional
    public Chat update(Long convoId, Long chatId, Long githubId, String content, String metadataJson) {
        Conversation c = requireOwnedConversation(convoId, githubId);
        Chat m = chats.findById(chatId)
                .orElseThrow(() -> new IllegalArgumentException("Chat message not found"));
        if (m.getConversation() == null || !Objects.equals(m.getConversation().getId(), c.getId())) {
            throw new SecurityException("Message does not belong to this conversation");
        }

        if (content != null && !content.isBlank()) m.setContent(content);
        if (metadataJson != null) m.setMetadataJson(metadataJson);

        // Update lastMessageAt to indicate activity
        c.setLastMessageAt(LocalDateTime.now());

        return m;
    }

    @Transactional
    public void delete(Long convoId, Long chatId, Long githubId) {
        Conversation c = requireOwnedConversation(convoId, githubId);
        Chat m = chats.findById(chatId)
                .orElseThrow(() -> new IllegalArgumentException("Chat message not found"));
        if (m.getConversation() == null || !Objects.equals(m.getConversation().getId(), c.getId())) {
            throw new SecurityException("Message does not belong to this conversation");
        }
        chats.delete(m);
        // Intentionally not updating lastMessageAt on delete
    }

    private Conversation requireOwnedConversation(Long convoId, Long githubId) {
        Conversation c = convos.findById(convoId)
                .orElseThrow(() -> new IllegalArgumentException("Conversation not found"));
        if (c.getUser() == null || !Objects.equals(c.getUser().getGithubId(), githubId)) {
            throw new SecurityException("Not your conversation");
        }
        return c;
    }
}
