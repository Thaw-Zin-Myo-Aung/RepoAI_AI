package com.example.audit.repository;

import com.example.audit.model.AuditLog;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.boot.test.autoconfigure.orm.jpa.TestEntityManager;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration tests for {@link AuditLogRepository}.
 *
 * <p>This test class uses {@code @DataJpaTest} to test the persistence layer,
 * focusing on the {@link AuditLogRepository} interface. It ensures that the
 * {@link AuditLog} entity is correctly mapped and that repository methods
 * function as expected.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@DataJpaTest
public class AuditLogRepositoryTest {

    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private AuditLogRepository auditLogRepository;

    /**
     * Tests if an AuditLog entity can be saved and then retrieved from the database.
     *
     * <p>This test verifies the basic CRUD functionality of the repository.
     * It persists an {@link AuditLog} entity, flushes the changes to the database,
     * and then attempts to retrieve it to ensure it was saved correctly.</p>
     */
    @Test
    public void whenSaveAuditLog_thenCanBeFound() {
        // Given: a new AuditLog entity
        AuditLog auditLog = new AuditLog();
        auditLog.setEventName("USER_LOGIN_SUCCESS");
        auditLog.setEventDescription("User 'testuser' logged in successfully.");
        auditLog.setEntityType("User");
        auditLog.setEntityId("123");
        auditLog.setUserId("testuser");
        auditLog.setTimestamp(LocalDateTime.now());
        auditLog.setDetails("{\"ipAddress\":\"127.0.0.1\"}");

        // When: the entity is persisted
        AuditLog savedAuditLog = entityManager.persistAndFlush(auditLog);

        // Then: the entity can be found in the repository
        Optional<AuditLog> foundAuditLog = auditLogRepository.findById(savedAuditLog.getId());

        // And: the found entity has the correct data
        assertThat(foundAuditLog).isPresent();
        assertThat(foundAuditLog.get().getEventName()).isEqualTo("USER_LOGIN_SUCCESS");
        assertThat(foundAuditLog.get().getUserId()).isEqualTo("testuser");
        assertThat(foundAuditLog.get().getEntityId()).isEqualTo("123");
    }
}
