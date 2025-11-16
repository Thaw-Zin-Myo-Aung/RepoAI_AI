package th.ac.mfu.repoai.repository;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

import th.ac.mfu.repoai.domain.Chat;

public interface ChatRepository extends JpaRepository<Chat, Long> {
    List<Chat> findByConversation_IdOrderByCreatedAtAsc(Long conversationId);
}
