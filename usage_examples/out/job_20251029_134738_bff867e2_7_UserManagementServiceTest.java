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

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * Unit tests for the UserManagementService.
 *
 * <p>This test class verifies the functionality of UserManagementService,
 * including user creation, update, and deletion, ensuring that audit logs
 * are correctly generated for each operation.</p>
 *
 * @see UserManagementService
 */
@ExtendWith(MockitoExtension.class)
class UserManagementServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private AuditLogRepository auditLogRepository;

    @InjectMocks
    private UserManagementService userService;

    private User user;

    /**
     * Sets up common test data and mock behavior before each test.
     */
    @BeforeEach
    void setUp() {
        user = new User();
        user.setId(1L);
        user.setUsername("testuser");
        user.setEmail("test@example.com");
    }

    /**
     * Tests the creation of a user and verifies that an audit log is saved.
     */
    @Test
    void testCreateUser() {
        // Arrange
        when(userRepository.save(any(User.class))).thenReturn(user);
        ArgumentCaptor<AuditLog> auditLogCaptor = ArgumentCaptor.forClass(AuditLog.class);

        // Act
        User createdUser = userService.createUser(user);

        // Assert
        assertNotNull(createdUser);
        assertEquals("testuser", createdUser.getUsername());
        verify(userRepository, times(1)).save(user);

        // Verify audit log
        verify(auditLogRepository, times(1)).save(auditLogCaptor.capture());
        AuditLog capturedLog = auditLogCaptor.getValue();
        assertEquals("CREATE", capturedLog.getAction());
        assertEquals(user.getId(), capturedLog.getUserId());
        assertTrue(capturedLog.getDetails().contains("Created user with username: testuser"));
        assertNotNull(capturedLog.getTimestamp());
    }

    /**
     * Tests the update of a user and verifies that an audit log is saved.
     */
    @Test
    void testUpdateUser() {
        // Arrange
        when(userRepository.findById(1L)).thenReturn(Optional.of(user));
        when(userRepository.save(any(User.class))).thenReturn(user);
        ArgumentCaptor<AuditLog> auditLogCaptor = ArgumentCaptor.forClass(AuditLog.class);

        User updatedDetails = new User();
        updatedDetails.setUsername("updateduser");
        updatedDetails.setEmail("updated@example.com");

        // Act
        User updatedUser = userService.updateUser(1L, updatedDetails);

        // Assert
        assertNotNull(updatedUser);
        assertEquals("updateduser", updatedUser.getUsername());
        verify(userRepository, times(1)).findById(1L);
        verify(userRepository, times(1)).save(user);

        // Verify audit log
        verify(auditLogRepository, times(1)).save(auditLogCaptor.capture());
        AuditLog capturedLog = auditLogCaptor.getValue();
        assertEquals("UPDATE", capturedLog.getAction());
        assertEquals(user.getId(), capturedLog.getUserId());
        assertTrue(capturedLog.getDetails().contains("Updated user with ID: 1"));
        assertNotNull(capturedLog.getTimestamp());
    }

    /**
     * Tests the deletion of a user and verifies that an audit log is saved.
     */
    @Test
    void testDeleteUser() {
        // Arrange
        when(userRepository.findById(1L)).thenReturn(Optional.of(user));
        doNothing().when(userRepository).delete(user);
        ArgumentCaptor<AuditLog> auditLogCaptor = ArgumentCaptor.forClass(AuditLog.class);

        // Act
        userService.deleteUser(1L);

        // Assert
        verify(userRepository, times(1)).findById(1L);
        verify(userRepository, times(1)).delete(user);

        // Verify audit log
        verify(auditLogRepository, times(1)).save(auditLogCaptor.capture());
        AuditLog capturedLog = auditLogCaptor.getValue();
        assertEquals("DELETE", capturedLog.getAction());
        assertEquals(user.getId(), capturedLog.getUserId());
        assertTrue(capturedLog.getDetails().contains("Deleted user with ID: 1"));
        assertNotNull(capturedLog.getTimestamp());
    }
}
