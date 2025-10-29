package com.example.service;

import com.example.model.AuditLog;
import com.example.model.User;
import com.example.repository.AuditLogRepository;
import com.example.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Optional;

/**
 * Service for managing users with audit logging.
 *
 * <p>This service handles the core business logic for user creation, updating,
 * and deletion. It also records audit trails for these actions.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Service
public class UserManagementService {

    private static final Logger logger = LoggerFactory.getLogger(UserManagementService.class);

    private final UserRepository userRepository;
    private final AuditLogRepository auditLogRepository;

    /**
     * Constructs a UserManagementService with the required repositories.
     *
     * @param userRepository     the repository for user data access
     * @param auditLogRepository the repository for audit log data access
     */
    @Autowired
    public UserManagementService(UserRepository userRepository, AuditLogRepository auditLogRepository) {
        this.userRepository = userRepository;
        this.auditLogRepository = auditLogRepository;
    }

    /**
     * Creates a new user and logs the action.
     *
     * @param user The user entity to create.
     * @return The persisted user entity.
     * @throws IllegalArgumentException if the user object is null.
     */
    @Transactional
    public User createUser(User user) {
        if (user == null) {
            throw new IllegalArgumentException("User cannot be null");
        }
        User savedUser = userRepository.save(user);
        logAudit("CREATE_USER", "User created with ID: " + savedUser.getId());
        return savedUser;
    }

    /**
     * Updates an existing user and logs the action.
     *
     * @param userId      The ID of the user to update.
     * @param userDetails The user object containing updated details.
     * @return An Optional containing the updated user, or an empty Optional if no user was found.
     * @throws IllegalArgumentException if userDetails is null.
     */
    @Transactional
    public Optional<User> updateUser(Long userId, User userDetails) {
        if (userDetails == null) {
            throw new IllegalArgumentException("User details cannot be null");
        }
        Optional<User> updatedUser = userRepository.findById(userId).map(user -> {
            user.setUsername(userDetails.getUsername());
            user.setEmail(userDetails.getEmail());
            // Assuming other fields are updated here as well
            return userRepository.save(user);
        });

        updatedUser.ifPresent(user -> logAudit("UPDATE_USER", "User updated with ID: " + user.getId()));

        return updatedUser;
    }

    /**
     * Deletes a user by their ID and logs the action.
     *
     * @param userId The ID of the user to delete.
     */
    @Transactional
    public void deleteUser(Long userId) {
        userRepository.deleteById(userId);
        logAudit("DELETE_USER", "User deleted with ID: " + userId);
    }

    /**
     * Helper method to create and persist an audit log.
     * The audit logging is wrapped in a try-catch block to ensure that any
     * failure in the auditing process does not affect the main business operation.
     *
     * @param action  The action being logged (e.g., "CREATE_USER").
     * @param details A description of the audited event.
     */
    private void logAudit(String action, String details) {
        try {
            AuditLog log = new AuditLog();
            log.setAction(action);
            log.setDetails(details);
            log.setTimestamp(LocalDateTime.now());
            // In a real application, you would set the user performing the action.
            // log.setPerformedBy("currentUser"); 
            auditLogRepository.save(log);
        } catch (Exception e) {
            // Log the audit failure but do not rethrow the exception
            // to avoid rolling back the main transaction.
            logger.error("Failed to save audit log for action: {}", action, e);
        }
    }
}
