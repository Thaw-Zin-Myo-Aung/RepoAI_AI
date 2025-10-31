package com.example.service;

import com.example.model.AuditLog;
import com.example.model.User;
import com.example.repository.AuditLogRepository;
import com.example.repository.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Service class for managing users with audit logging.
 *
 * <p>This service handles the business logic for user creation, updates,
 * and deletion, and records these actions in an audit log.</p>
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
     * Constructs the UserManagementService with required repositories.
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
     * @param user the user to create
     * @return the created user
     */
    @Transactional
    public User createUser(User user) {
        User savedUser = userRepository.save(user);
        logAuditAction("CREATE_USER", savedUser.getId(), "User created with username: " + savedUser.getUsername());
        return savedUser;
    }

    /**
     * Updates an existing user and logs the action.
     *
     * @param userId      the ID of the user to update
     * @param userDetails the new details for the user
     * @return an Optional containing the updated user, or empty if the user was not found
     */
    @Transactional
    public Optional<User> updateUser(Long userId, User userDetails) {
        return userRepository.findById(userId).map(user -> {
            user.setUsername(userDetails.getUsername());
            user.setEmail(userDetails.getEmail());
            User updatedUser = userRepository.save(user);
            logAuditAction("UPDATE_USER", updatedUser.getId(), "User details updated for username: " + updatedUser.getUsername());
            return updatedUser;
        });
    }

    /**
     * Deletes a user by their ID and logs the action.
     *
     * @param userId the ID of the user to delete
     */
    @Transactional
    public void deleteUser(Long userId) {
        logAuditAction("DELETE_USER", userId, "Attempting to delete user with ID: " + userId);
        userRepository.deleteById(userId);
    }

    /**
     * Retrieves a user by their ID.
     *
     * @param userId the ID of the user to retrieve
     * @return an Optional containing the user if found, or empty otherwise
     */
    public Optional<User> getUserById(Long userId) {
        return userRepository.findById(userId);
    }

    /**
     * Retrieves all users.
     *
     * @return a list of all users
     */
    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    /**
     * Logs an audit action performed by a user.
     * <p>
     * Retrieves the current authenticated user's name from the SecurityContext
     * to use as the actor for the audit log entry.
     *
     * @param action       the action performed (e.g., "CREATE_USER")
     * @param targetUserId the ID of the user being acted upon
     * @param details      a description of the action
     */
    private void logAuditAction(String action, Long targetUserId, String details) {
        try {
            Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
            String actorUsername = (authentication != null) ? authentication.getName() : "SYSTEM";

            AuditLog log = new AuditLog();
            // In a real application, you might look up an actor ID from the username.
            // For simplicity, we are storing the username.
            log.setActorUsername(actorUsername);
            log.setAction(action);
            log.setTargetUserId(targetUserId);
            log.setTimestamp(LocalDateTime.now());
            log.setDetails(details);

            auditLogRepository.save(log);
            logger.debug("Audit log created for action '{}' by actor '{}'", action, actorUsername);
        } catch (Exception e) {
            logger.error("Failed to save audit log for action: {}", action, e);
            // Depending on business requirements, you might re-throw this as a custom exception
            // or simply log it without interrupting the main operation.
        }
    }
}
