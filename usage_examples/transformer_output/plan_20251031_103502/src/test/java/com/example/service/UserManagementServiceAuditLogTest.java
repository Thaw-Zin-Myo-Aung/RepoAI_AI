package com.example.service;

import com.example.model.AuditLog;
import com.example.model.User;
import com.example.repository.AuditLogRepository;
import com.example.repository.UserRepository;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Integration test for {@link UserManagementService} focusing on audit log creation.
 *
 * <p>This test class verifies that for each user management operation (create, update, delete),
 * an appropriate audit log is persisted in the database. It uses a mocked security context
 * to provide a consistent actor ID for all audited actions.</p>
 *
 * <p>Tests are transactional and will be rolled back after execution to ensure no
 * side effects on the test database.</p>
 *
 * @see UserManagementService
 * @see com.example.model.AuditLog
 */
@SpringBootTest
@Transactional
class UserManagementServiceAuditLogTest {

    @Autowired
    private UserManagementService userManagementService;

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private AuditLogRepository auditLogRepository;

    private static final String ACTOR_ID = "test-actor-123";

    /**
     * Sets up the security context before each test.
     * This is necessary to simulate an authenticated user performing the actions,
     * which provides the 'actorId' required for creating audit logs.
     */
    @BeforeEach
    void setUp() {
        // Create a simple authentication token for testing purposes
        UsernamePasswordAuthenticationToken authentication = new UsernamePasswordAuthenticationToken(
                ACTOR_ID, null, List.of());
        
        // Set the mocked context in the SecurityContextHolder
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    /**
     * Clears the security context after each test to ensure test isolation.
     */
    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    /**
     * Verifies that creating a user also creates a corresponding audit log.
     */
    @Test
    @DisplayName("Create User Should Persist Audit Log")
    void testCreateUser_ShouldCreateAuditLog() {
        // Given
        User newUser = new User();
        newUser.setUsername("audit-test-user");
        newUser.setEmail("audit-test-user@example.com");
        newUser.setPassword("securePassword123");

        long initialAuditCount = auditLogRepository.count();

        // When
        User createdUser = userManagementService.createUser(newUser);

        // Then
        assertThat(createdUser).isNotNull();
        assertThat(createdUser.getId()).isNotNull();

        List<AuditLog> auditLogs = auditLogRepository.findAll();
        assertThat(auditLogs).hasSize((int) initialAuditCount + 1);

        // Find the specific audit log for this action
        Optional<AuditLog> createdAuditLog = auditLogs.stream()
                .filter(log -> log.getEntityId().equals(createdUser.getId()) && "CREATE_USER".equals(log.getAction()))
                .findFirst();

        assertThat(createdAuditLog).isPresent();
        AuditLog auditLog = createdAuditLog.get();
        assertThat(auditLog.getAction()).isEqualTo("CREATE_USER");
        assertThat(auditLog.getEntityId()).isEqualTo(createdUser.getId());
        assertThat(auditLog.getActorId()).isEqualTo(ACTOR_ID);
        assertThat(auditLog.getDetails()).contains("\"username\":\"audit-test-user\"");
    }

    /**
     * Verifies that updating a user also creates a corresponding audit log.
     */
    @Test
    @DisplayName("Update User Should Persist Audit Log")
    void testUpdateUser_ShouldCreateAuditLog() {
        // Given: Create an initial user to update
        User user = new User();
        user.setUsername("original-user");
        user.setEmail("original@example.com");
        user.setPassword("password");
        User savedUser = userRepository.saveAndFlush(user);
        
        long initialAuditCount = auditLogRepository.count();

        // When: Update the user's username
        savedUser.setUsername("updated-user");
        userManagementService.updateUser(savedUser.getId(), savedUser);

        // Then
        Optional<User> updatedUserOpt = userRepository.findById(savedUser.getId());
        assertThat(updatedUserOpt).isPresent();
        assertThat(updatedUserOpt.get().getUsername()).isEqualTo("updated-user");

        List<AuditLog> auditLogs = auditLogRepository.findAll();
        assertThat(auditLogs).hasSize((int) initialAuditCount + 1);

        Optional<AuditLog> updatedAuditLog = auditLogs.stream()
                .filter(log -> log.getEntityId().equals(savedUser.getId()) && "UPDATE_USER".equals(log.getAction()))
                .findFirst();

        assertThat(updatedAuditLog).isPresent();
        AuditLog auditLog = updatedAuditLog.get();
        assertThat(auditLog.getAction()).isEqualTo("UPDATE_USER");
        assertThat(auditLog.getEntityId()).isEqualTo(savedUser.getId());
        assertThat(auditLog.getActorId()).isEqualTo(ACTOR_ID);
        assertThat(auditLog.getDetails()).contains("\"username\":\"updated-user\"");
    }

    /**
     * Verifies that deleting a user also creates a corresponding audit log.
     */
    @Test
    @DisplayName("Delete User Should Persist Audit Log")
    void testDeleteUser_ShouldCreateAuditLog() {
        // Given: Create a user to delete
        User user = new User();
        user.setUsername("delete-user");
        user.setEmail("delete@example.com");
        user.setPassword("password");
        User savedUser = userRepository.saveAndFlush(user);
        Long userId = savedUser.getId();

        long initialAuditCount = auditLogRepository.count();

        // When
        userManagementService.deleteUser(userId);

        // Then
        Optional<User> deletedUser = userRepository.findById(userId);
        assertThat(deletedUser).isEmpty(); // Assuming hard delete

        List<AuditLog> auditLogs = auditLogRepository.findAll();
        assertThat(auditLogs).hasSize((int) initialAuditCount + 1);

        Optional<AuditLog> deletedAuditLog = auditLogs.stream()
                .filter(log -> log.getEntityId().equals(userId) && "DELETE_USER".equals(log.getAction()))
                .findFirst();
        
        assertThat(deletedAuditLog).isPresent();
        AuditLog auditLog = deletedAuditLog.get();
        assertThat(auditLog.getAction()).isEqualTo("DELETE_USER");
        assertThat(auditLog.getEntityId()).isEqualTo(userId);
        assertThat(auditLog.getActorId()).isEqualTo(ACTOR_ID);
    }
}
