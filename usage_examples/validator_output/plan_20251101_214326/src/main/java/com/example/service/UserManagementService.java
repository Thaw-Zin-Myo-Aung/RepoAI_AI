package com.example.service;

import com.example.model.AuditLog;
import com.example.model.User;
import com.example.repository.AuditLogRepository;
import com.example.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

/**
 * Service class for managing users with audit logging.
 *
 * <p>This service handles the business logic for user creation, updating, deletion,
 * and retrieval. It also logs these actions for auditing purposes.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Service
public class UserManagementService {

    private final UserRepository userRepository;
    private final AuditLogRepository auditLogRepository;

    /**
     * Constructs a new UserManagementService with the required repositories.
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
     * @param user the user entity to create
     * @return the newly created and saved user entity
     * @throws IllegalArgumentException if the user is null
     */
    @Transactional
    public User createUser(User user) {
        if (user == null) {
            throw new IllegalArgumentException("User cannot be null");
        }
        User savedUser = userRepository.save(user);

        // Create and save an audit log
        AuditLog auditLog = new AuditLog();
        auditLog.setAction("CREATE_USER");
        auditLog.setDetails("Created user with ID: " + savedUser.getId() + " and username: " + savedUser.getUsername());
        auditLog.setTimestamp(LocalDateTime.now());
        auditLog.setUserId(savedUser.getId());
        auditLogRepository.save(auditLog);

        return savedUser;
    }

    /**
     * Updates an existing user and logs the action.
     *
     * @param id          the ID of the user to update
     * @param userDetails the new details for the user
     * @return an {@link Optional} containing the updated user if found, otherwise empty
     * @throws IllegalArgumentException if userDetails is null
     */
    @Transactional
    public Optional<User> updateUser(Long id, User userDetails) {
        if (userDetails == null) {
            throw new IllegalArgumentException("User details cannot be null");
        }
        return userRepository.findById(id).map(user -> {
            user.setUsername(userDetails.getUsername());
            user.setEmail(userDetails.getEmail());
            User updatedUser = userRepository.save(user);

            // Create and save an audit log
            AuditLog auditLog = new AuditLog();
            auditLog.setAction("UPDATE_USER");
            auditLog.setDetails("Updated user with ID: " + updatedUser.getId());
            auditLog.setTimestamp(LocalDateTime.now());
            auditLog.setUserId(updatedUser.getId());
            auditLogRepository.save(auditLog);

            return updatedUser;
        });
    }

    /**
     * Deletes a user by their ID and logs the action.
     *
     * @param id the ID of the user to delete
     * @throws org.springframework.dao.EmptyResultDataAccessException if no user with the given id exists.
     */
    @Transactional
    public void deleteUser(Long id) {
        // Log the action before deleting
        AuditLog auditLog = new AuditLog();
        auditLog.setAction("DELETE_USER");
        auditLog.setDetails("Attempting to delete user with ID: " + id);
        auditLog.setTimestamp(LocalDateTime.now());
        auditLog.setUserId(id); // The user ID that is being deleted
        auditLogRepository.save(auditLog);

        userRepository.deleteById(id);
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
     * Retrieves a user by their ID.
     *
     * @param id the ID of the user to retrieve
     * @return an Optional containing the user if found, or empty otherwise
     */
    public Optional<User> getUserById(Long id) {
        return userRepository.findById(id);
    }
}
