package com.example.service;

import com.example.model.AuditLog;
import com.example.model.User;
import com.example.repository.AuditLogRepository;
import com.example.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * Unit tests for the auditing functionality of UserManagementService.
 *
 * <p>This test class verifies that for each user management action (create, update, delete),
 * an audit log is correctly created and saved. It uses Mockito to mock repository
 * dependencies and an ArgumentCaptor to inspect the arguments passed to the save method.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@ExtendWith(MockitoExtension.class)
class UserManagementServiceAuditTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private AuditLogRepository auditLogRepository;

    @InjectMocks
    private UserManagementService userManagementService;

    private User user;

    /**
     * Sets up a sample user object before each test.
     */
    @BeforeEach
    void setUp() {
        user = new User();
        user.setId(1L);
        user.setUsername("testuser");
        user.setEmail("test@example.com");
    }

    /**
     * Verifies that creating a user triggers an audit log with the 'CREATE' action.
     *
     * <p>This test ensures that when {@link UserManagementService#createUser(User)} is called,
     * the {@link AuditLogRepository#save(AuditLog)} method is invoked exactly once.
     * It captures the {@link AuditLog} object and asserts that its actionType is "CREATE"
     * and its details contain the new user's information.</p>
     */
    @Test
    void whenCreateUser_thenAuditLogIsSavedWithCreateAction() {
        // Given
        when(userRepository.save(any(User.class))).thenReturn(user);
        ArgumentCaptor<AuditLog> auditLogCaptor = ArgumentCaptor.forClass(AuditLog.class);

        // When
        userManagementService.createUser(user);

        // Then
        verify(auditLogRepository, times(1)).save(auditLogCaptor.capture());
        AuditLog capturedAuditLog = auditLogCaptor.getValue();

        assertEquals("CREATE", capturedAuditLog.getActionType());
        assertTrue(capturedAuditLog.getDetails().contains("Created user with ID: 1"));
    }

    /**
     * Verifies that updating a user triggers an audit log with the 'UPDATE' action.
     *
     * <p>This test ensures that when {@link UserManagementService#updateUser(Long, User)} is called,
     * the {@link AuditLogRepository#save(AuditLog)} method is invoked exactly once.
     * It captures the {@link AuditLog} object and asserts that its actionType is "UPDATE"
     * and its details contain the updated user's information.</p>
     */
    @Test
    void whenUpdateUser_thenAuditLogIsSavedWithUpdateAction() {
        // Given
        User updatedDetails = new User();
        updatedDetails.setUsername("updateduser");
        updatedDetails.setEmail("updated@example.com");

        when(userRepository.findById(1L)).thenReturn(Optional.of(user));
        when(userRepository.save(any(User.class))).thenReturn(user);
        ArgumentCaptor<AuditLog> auditLogCaptor = ArgumentCaptor.forClass(AuditLog.class);

        // When
        userManagementService.updateUser(1L, updatedDetails);

        // Then
        verify(auditLogRepository, times(1)).save(auditLogCaptor.capture());
        AuditLog capturedAuditLog = auditLogCaptor.getValue();

        assertEquals("UPDATE", capturedAuditLog.getActionType());
        assertTrue(capturedAuditLog.getDetails().contains("Updated user with ID: 1"));
    }

    /**
     * Verifies that deleting a user triggers an audit log with the 'DELETE' action.
     *
     * <p>This test ensures that when {@link UserManagementService#deleteUser(Long)} is called,
     * the {@link AuditLogRepository#save(AuditLog)} method is invoked exactly once.
     * It captures the {@link AuditLog} object and asserts that its actionType is "DELETE"
     * and its details contain the deleted user's ID.</p>
     */
    @Test
    void whenDeleteUser_thenAuditLogIsSavedWithDeleteAction() {
        // Given
        when(userRepository.findById(1L)).thenReturn(Optional.of(user));
        doNothing().when(userRepository).deleteById(1L);
        ArgumentCaptor<AuditLog> auditLogCaptor = ArgumentCaptor.forClass(AuditLog.class);

        // When
        userManagementService.deleteUser(1L);

        // Then
        verify(auditLogRepository, times(1)).save(auditLogCaptor.capture());
        AuditLog capturedAuditLog = auditLogCaptor.getValue();

        assertEquals("DELETE", capturedAuditLog.getActionType());
        assertTrue(capturedAuditLog.getDetails().contains("Deleted user with ID: 1"));
    }
}
