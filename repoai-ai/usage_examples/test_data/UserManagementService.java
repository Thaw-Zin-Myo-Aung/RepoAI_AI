package com.example.auth.service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.stream.Collectors;

import javax.validation.Valid;
import javax.validation.constraints.Email;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Size;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.annotation.CacheEvict;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import com.example.auth.dto.ChangePasswordRequest;
import com.example.auth.dto.CreateUserRequest;
import com.example.auth.dto.UpdateUserRequest;
import com.example.auth.dto.UserDTO;
import com.example.auth.entity.Role;
import com.example.auth.entity.User;
import com.example.auth.entity.UserStatus;
import com.example.auth.exception.DuplicateUserException;
import com.example.auth.exception.InvalidPasswordException;
import com.example.auth.exception.UserNotFoundException;
import com.example.auth.repository.RoleRepository;
import com.example.auth.repository.UserRepository;
import com.example.auth.security.JwtTokenProvider;
import com.example.notification.service.EmailService;

import lombok.extern.slf4j.Slf4j;

/**
 * Service class for managing user operations.
 * Provides user CRUD operations, authentication, and authorization functionality.
 * 
 * @author Development Team
 * @version 1.0
 * @since 2024-01-01
 */
@Slf4j
@Service
@Transactional
public class UserManagementService implements UserDetailsService {

    @Autowired
    private UserRepository userRepository;

    @Autowired
    private RoleRepository roleRepository;

    @Autowired
    private PasswordEncoder passwordEncoder;

    @Autowired
    private JwtTokenProvider jwtTokenProvider;

    @Autowired
    private EmailService emailService;

    @Value("${app.security.password.min-length:8}")
    private int minPasswordLength;

    @Value("${app.security.password.max-attempts:5}")
    private int maxLoginAttempts;

    @Value("${app.security.account.lock-duration:30}")
    private int accountLockDurationMinutes;

    @Value("${app.security.session.timeout:3600}")
    private int sessionTimeoutSeconds;

    private static final String DEFAULT_ROLE = "ROLE_USER";
    private static final String ADMIN_ROLE = "ROLE_ADMIN";
    private static final String CACHE_NAME = "users";

    /**
     * Creates a new user in the system.
     * 
     * @param request the user creation request containing user details
     * @return the created user DTO
     * @throws DuplicateUserException if user with same email already exists
     */
    @PreAuthorize("hasRole('ADMIN')")
    @CacheEvict(value = CACHE_NAME, allEntries = true)
    public UserDTO createUser(@Valid CreateUserRequest request) {
        log.info("Creating new user with email: {}", request.getEmail());

        // Check if user already exists
        if (userRepository.existsByEmail(request.getEmail())) {
            log.error("User with email {} already exists", request.getEmail());
            throw new DuplicateUserException("User with email " + request.getEmail() + " already exists");
        }

        if (userRepository.existsByUsername(request.getUsername())) {
            log.error("User with username {} already exists", request.getUsername());
            throw new DuplicateUserException("User with username " + request.getUsername() + " already exists");
        }

        // Validate password strength
        validatePasswordStrength(request.getPassword());

        // Create new user entity
        User user = new User();
        user.setUsername(request.getUsername());
        user.setEmail(request.getEmail());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setFirstName(request.getFirstName());
        user.setLastName(request.getLastName());
        user.setPhoneNumber(request.getPhoneNumber());
        user.setStatus(UserStatus.ACTIVE);
        user.setCreatedAt(LocalDateTime.now());
        user.setUpdatedAt(LocalDateTime.now());
        user.setEmailVerified(false);
        user.setLoginAttempts(0);

        // Assign default role
        Role defaultRole = roleRepository.findByName(DEFAULT_ROLE)
                .orElseThrow(() -> new IllegalStateException("Default role not found"));
        user.getRoles().add(defaultRole);

        // Save user
        User savedUser = userRepository.save(user);
        log.info("User created successfully with ID: {}", savedUser.getId());

        // Send welcome email
        sendWelcomeEmail(savedUser);

        return convertToDTO(savedUser);
    }

    /**
     * Updates an existing user's information.
     * 
     * @param userId the ID of the user to update
     * @param request the update request containing new user details
     * @return the updated user DTO
     * @throws UserNotFoundException if user is not found
     */
    @PreAuthorize("hasRole('ADMIN') or #userId == authentication.principal.id")
    @CacheEvict(value = CACHE_NAME, key = "#userId")
    public UserDTO updateUser(Long userId, @Valid UpdateUserRequest request) {
        log.info("Updating user with ID: {}", userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        // Update fields
        if (StringUtils.hasText(request.getFirstName())) {
            user.setFirstName(request.getFirstName());
        }
        if (StringUtils.hasText(request.getLastName())) {
            user.setLastName(request.getLastName());
        }
        if (StringUtils.hasText(request.getPhoneNumber())) {
            user.setPhoneNumber(request.getPhoneNumber());
        }

        user.setUpdatedAt(LocalDateTime.now());

        User updatedUser = userRepository.save(user);
        log.info("User updated successfully: {}", userId);

        return convertToDTO(updatedUser);
    }

    /**
     * Retrieves a user by their ID.
     * 
     * @param userId the ID of the user
     * @return the user DTO
     * @throws UserNotFoundException if user is not found
     */
    @Cacheable(value = CACHE_NAME, key = "#userId")
    public UserDTO getUserById(Long userId) {
        log.debug("Retrieving user with ID: {}", userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        return convertToDTO(user);
    }

    /**
     * Retrieves a user by their email address.
     * 
     * @param email the email address
     * @return the user DTO
     * @throws UserNotFoundException if user is not found
     */
    @Cacheable(value = CACHE_NAME, key = "#email")
    public UserDTO getUserByEmail(String email) {
        log.debug("Retrieving user with email: {}", email);

        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UserNotFoundException("User not found with email: " + email));

        return convertToDTO(user);
    }

    /**
     * Retrieves all users with pagination.
     * 
     * @param pageable pagination information
     * @return page of user DTOs
     */
    @PreAuthorize("hasRole('ADMIN')")
    public Page<UserDTO> getAllUsers(Pageable pageable) {
        log.debug("Retrieving all users with pagination");

        Page<User> users = userRepository.findAll(pageable);
        return users.map(this::convertToDTO);
    }

    /**
     * Searches users by various criteria.
     * 
     * @param searchTerm the search term
     * @param pageable pagination information
     * @return page of matching user DTOs
     */
    @PreAuthorize("hasRole('ADMIN')")
    public Page<UserDTO> searchUsers(String searchTerm, Pageable pageable) {
        log.debug("Searching users with term: {}", searchTerm);

        Page<User> users = userRepository.searchUsers(searchTerm, pageable);
        return users.map(this::convertToDTO);
    }

    /**
     * Deletes a user by their ID.
     * 
     * @param userId the ID of the user to delete
     * @throws UserNotFoundException if user is not found
     */
    @PreAuthorize("hasRole('ADMIN')")
    @CacheEvict(value = CACHE_NAME, key = "#userId")
    public void deleteUser(Long userId) {
        log.info("Deleting user with ID: {}", userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        // Soft delete
        user.setStatus(UserStatus.DELETED);
        user.setUpdatedAt(LocalDateTime.now());
        userRepository.save(user);

        log.info("User deleted successfully: {}", userId);
    }

    /**
     * Changes a user's password.
     * 
     * @param userId the ID of the user
     * @param request the password change request
     * @throws UserNotFoundException if user is not found
     * @throws InvalidPasswordException if old password is incorrect
     */
    @PreAuthorize("#userId == authentication.principal.id")
    @CacheEvict(value = CACHE_NAME, key = "#userId")
    public void changePassword(Long userId, @Valid ChangePasswordRequest request) {
        log.info("Changing password for user: {}", userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        // Verify old password
        if (!passwordEncoder.matches(request.getOldPassword(), user.getPassword())) {
            log.error("Invalid old password for user: {}", userId);
            throw new InvalidPasswordException("Old password is incorrect");
        }

        // Validate new password
        validatePasswordStrength(request.getNewPassword());

        // Check if new password is different from old
        if (passwordEncoder.matches(request.getNewPassword(), user.getPassword())) {
            throw new InvalidPasswordException("New password must be different from old password");
        }

        // Update password
        user.setPassword(passwordEncoder.encode(request.getNewPassword()));
        user.setPasswordChangedAt(LocalDateTime.now());
        user.setUpdatedAt(LocalDateTime.now());
        userRepository.save(user);

        log.info("Password changed successfully for user: {}", userId);

        // Send notification email
        sendPasswordChangedEmail(user);
    }

    /**
     * Resets a user's password.
     * 
     * @param email the user's email address
     * @return the password reset token
     * @throws UserNotFoundException if user is not found
     */
    public String resetPassword(String email) {
        log.info("Initiating password reset for email: {}", email);

        User user = userRepository.findByEmail(email)
                .orElseThrow(() -> new UserNotFoundException("User not found with email: " + email));

        // Generate reset token
        String resetToken = UUID.randomUUID().toString();
        user.setPasswordResetToken(resetToken);
        user.setPasswordResetTokenExpiryDate(LocalDateTime.now().plusHours(24));
        userRepository.save(user);

        // Send reset email
        sendPasswordResetEmail(user, resetToken);

        log.info("Password reset token generated for user: {}", user.getId());
        return resetToken;
    }

    /**
     * Confirms password reset with token.
     * 
     * @param token the reset token
     * @param newPassword the new password
     * @throws IllegalArgumentException if token is invalid or expired
     */
    public void confirmPasswordReset(String token, String newPassword) {
        log.info("Confirming password reset with token");

        User user = userRepository.findByPasswordResetToken(token)
                .orElseThrow(() -> new IllegalArgumentException("Invalid password reset token"));

        // Check token expiry
        if (user.getPasswordResetTokenExpiryDate().isBefore(LocalDateTime.now())) {
            throw new IllegalArgumentException("Password reset token has expired");
        }

        // Validate new password
        validatePasswordStrength(newPassword);

        // Update password
        user.setPassword(passwordEncoder.encode(newPassword));
        user.setPasswordResetToken(null);
        user.setPasswordResetTokenExpiryDate(null);
        user.setPasswordChangedAt(LocalDateTime.now());
        user.setUpdatedAt(LocalDateTime.now());
        userRepository.save(user);

        log.info("Password reset confirmed for user: {}", user.getId());
    }

    /**
     * Assigns a role to a user.
     * 
     * @param userId the user ID
     * @param roleName the role name to assign
     * @throws UserNotFoundException if user is not found
     */
    @PreAuthorize("hasRole('ADMIN')")
    @CacheEvict(value = CACHE_NAME, key = "#userId")
    public void assignRole(Long userId, String roleName) {
        log.info("Assigning role {} to user {}", roleName, userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        Role role = roleRepository.findByName(roleName)
                .orElseThrow(() -> new IllegalArgumentException("Role not found: " + roleName));

        user.getRoles().add(role);
        userRepository.save(user);

        log.info("Role assigned successfully");
    }

    /**
     * Removes a role from a user.
     * 
     * @param userId the user ID
     * @param roleName the role name to remove
     * @throws UserNotFoundException if user is not found
     */
    @PreAuthorize("hasRole('ADMIN')")
    @CacheEvict(value = CACHE_NAME, key = "#userId")
    public void removeRole(Long userId, String roleName) {
        log.info("Removing role {} from user {}", roleName, userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        Role role = roleRepository.findByName(roleName)
                .orElseThrow(() -> new IllegalArgumentException("Role not found: " + roleName));

        user.getRoles().remove(role);
        userRepository.save(user);

        log.info("Role removed successfully");
    }

    /**
     * Locks a user account.
     * 
     * @param userId the user ID
     * @throws UserNotFoundException if user is not found
     */
    @PreAuthorize("hasRole('ADMIN')")
    @CacheEvict(value = CACHE_NAME, key = "#userId")
    public void lockAccount(Long userId) {
        log.info("Locking account for user: {}", userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        user.setStatus(UserStatus.LOCKED);
        user.setAccountLockedAt(LocalDateTime.now());
        user.setUpdatedAt(LocalDateTime.now());
        userRepository.save(user);

        log.info("Account locked successfully");
    }

    /**
     * Unlocks a user account.
     * 
     * @param userId the user ID
     * @throws UserNotFoundException if user is not found
     */
    @PreAuthorize("hasRole('ADMIN')")
    @CacheEvict(value = CACHE_NAME, key = "#userId")
    public void unlockAccount(Long userId) {
        log.info("Unlocking account for user: {}", userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        user.setStatus(UserStatus.ACTIVE);
        user.setLoginAttempts(0);
        user.setAccountLockedAt(null);
        user.setUpdatedAt(LocalDateTime.now());
        userRepository.save(user);

        log.info("Account unlocked successfully");
    }

    /**
     * Records a failed login attempt.
     * 
     * @param email the user's email
     */
    public void recordFailedLoginAttempt(String email) {
        log.debug("Recording failed login attempt for: {}", email);

        userRepository.findByEmail(email).ifPresent(user -> {
            int attempts = user.getLoginAttempts() + 1;
            user.setLoginAttempts(attempts);
            user.setLastFailedLoginAt(LocalDateTime.now());

            if (attempts >= maxLoginAttempts) {
                log.warn("Max login attempts reached for user: {}", user.getId());
                user.setStatus(UserStatus.LOCKED);
                user.setAccountLockedAt(LocalDateTime.now());
                sendAccountLockedEmail(user);
            }

            userRepository.save(user);
        });
    }

    /**
     * Records a successful login.
     * 
     * @param email the user's email
     */
    public void recordSuccessfulLogin(String email) {
        log.debug("Recording successful login for: {}", email);

        userRepository.findByEmail(email).ifPresent(user -> {
            user.setLoginAttempts(0);
            user.setLastLoginAt(LocalDateTime.now());
            user.setUpdatedAt(LocalDateTime.now());
            userRepository.save(user);
        });
    }

    /**
     * Verifies a user's email address.
     * 
     * @param token the verification token
     * @throws IllegalArgumentException if token is invalid
     */
    public void verifyEmail(String token) {
        log.info("Verifying email with token");

        User user = userRepository.findByEmailVerificationToken(token)
                .orElseThrow(() -> new IllegalArgumentException("Invalid email verification token"));

        user.setEmailVerified(true);
        user.setEmailVerificationToken(null);
        user.setEmailVerifiedAt(LocalDateTime.now());
        user.setUpdatedAt(LocalDateTime.now());
        userRepository.save(user);

        log.info("Email verified for user: {}", user.getId());
    }

    /**
     * Sends an email verification token to a user.
     * 
     * @param userId the user ID
     * @throws UserNotFoundException if user is not found
     */
    public void sendEmailVerification(Long userId) {
        log.info("Sending email verification for user: {}", userId);

        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        String verificationToken = UUID.randomUUID().toString();
        user.setEmailVerificationToken(verificationToken);
        userRepository.save(user);

        sendEmailVerificationEmail(user, verificationToken);

        log.info("Email verification sent to: {}", user.getEmail());
    }

    /**
     * Gets the currently authenticated user.
     * 
     * @return the current user DTO
     * @throws UserNotFoundException if user is not found
     */
    public UserDTO getCurrentUser() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        String email = authentication.getName();

        return getUserByEmail(email);
    }

    /**
     * Checks if a user has a specific role.
     * 
     * @param userId the user ID
     * @param roleName the role name
     * @return true if user has the role, false otherwise
     */
    public boolean hasRole(Long userId, String roleName) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new UserNotFoundException("User not found with ID: " + userId));

        return user.getRoles().stream()
                .anyMatch(role -> role.getName().equals(roleName));
    }

    /**
     * Gets active user count.
     * 
     * @return the number of active users
     */
    @PreAuthorize("hasRole('ADMIN')")
    public long getActiveUserCount() {
        return userRepository.countByStatus(UserStatus.ACTIVE);
    }

    /**
     * Gets users by status.
     * 
     * @param status the user status
     * @param pageable pagination information
     * @return page of user DTOs
     */
    @PreAuthorize("hasRole('ADMIN')")
    public Page<UserDTO> getUsersByStatus(UserStatus status, Pageable pageable) {
        Page<User> users = userRepository.findByStatus(status, pageable);
        return users.map(this::convertToDTO);
    }

    /**
     * Gets recently registered users.
     * 
     * @param days number of days to look back
     * @return list of user DTOs
     */
    @PreAuthorize("hasRole('ADMIN')")
    public List<UserDTO> getRecentlyRegisteredUsers(int days) {
        LocalDateTime since = LocalDateTime.now().minusDays(days);
        List<User> users = userRepository.findByCreatedAtAfter(since);
        return users.stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    /**
     * Gets user statistics.
     * 
     * @return map of statistics
     */
    @PreAuthorize("hasRole('ADMIN')")
    public Map<String, Object> getUserStatistics() {
        Map<String, Object> stats = new HashMap<>();
        stats.put("totalUsers", userRepository.count());
        stats.put("activeUsers", userRepository.countByStatus(UserStatus.ACTIVE));
        stats.put("lockedUsers", userRepository.countByStatus(UserStatus.LOCKED));
        stats.put("deletedUsers", userRepository.countByStatus(UserStatus.DELETED));
        stats.put("verifiedUsers", userRepository.countByEmailVerified(true));
        stats.put("unverifiedUsers", userRepository.countByEmailVerified(false));

        return stats;
    }

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        log.debug("Loading user by username: {}", username);

        User user = userRepository.findByEmail(username)
                .orElseThrow(() -> new UsernameNotFoundException("User not found with email: " + username));

        if (user.getStatus() == UserStatus.LOCKED) {
            throw new UsernameNotFoundException("User account is locked");
        }

        if (user.getStatus() == UserStatus.DELETED) {
            throw new UsernameNotFoundException("User account is deleted");
        }

        List<GrantedAuthority> authorities = user.getRoles().stream()
                .map(role -> new SimpleGrantedAuthority(role.getName()))
                .collect(Collectors.toList());

        return org.springframework.security.core.userdetails.User.builder()
                .username(user.getEmail())
                .password(user.getPassword())
                .authorities(authorities)
                .accountExpired(false)
                .accountLocked(user.getStatus() == UserStatus.LOCKED)
                .credentialsExpired(false)
                .disabled(user.getStatus() != UserStatus.ACTIVE)
                .build();
    }

    private void validatePasswordStrength(String password) {
        if (password == null || password.length() < minPasswordLength) {
            throw new InvalidPasswordException(
                    "Password must be at least " + minPasswordLength + " characters long");
        }

        boolean hasUpperCase = password.chars().anyMatch(Character::isUpperCase);
        boolean hasLowerCase = password.chars().anyMatch(Character::isLowerCase);
        boolean hasDigit = password.chars().anyMatch(Character::isDigit);
        boolean hasSpecial = password.chars().anyMatch(ch -> "!@#$%^&*()_+-=[]{}|;:,.<>?".indexOf(ch) >= 0);

        if (!hasUpperCase || !hasLowerCase || !hasDigit || !hasSpecial) {
            throw new InvalidPasswordException(
                    "Password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character");
        }
    }

    private UserDTO convertToDTO(User user) {
        UserDTO dto = new UserDTO();
        dto.setId(user.getId());
        dto.setUsername(user.getUsername());
        dto.setEmail(user.getEmail());
        dto.setFirstName(user.getFirstName());
        dto.setLastName(user.getLastName());
        dto.setPhoneNumber(user.getPhoneNumber());
        dto.setStatus(user.getStatus().toString());
        dto.setEmailVerified(user.isEmailVerified());
        dto.setCreatedAt(user.getCreatedAt());
        dto.setUpdatedAt(user.getUpdatedAt());
        dto.setLastLoginAt(user.getLastLoginAt());

        List<String> roleNames = user.getRoles().stream()
                .map(Role::getName)
                .collect(Collectors.toList());
        dto.setRoles(roleNames);

        return dto;
    }

    private void sendWelcomeEmail(User user) {
        try {
            emailService.sendWelcomeEmail(user.getEmail(), user.getFirstName());
        } catch (Exception e) {
            log.error("Failed to send welcome email to: {}", user.getEmail(), e);
        }
    }

    private void sendPasswordChangedEmail(User user) {
        try {
            emailService.sendPasswordChangedNotification(user.getEmail(), user.getFirstName());
        } catch (Exception e) {
            log.error("Failed to send password changed email to: {}", user.getEmail(), e);
        }
    }

    private void sendPasswordResetEmail(User user, String token) {
        try {
            emailService.sendPasswordResetEmail(user.getEmail(), user.getFirstName(), token);
        } catch (Exception e) {
            log.error("Failed to send password reset email to: {}", user.getEmail(), e);
        }
    }

    private void sendEmailVerificationEmail(User user, String token) {
        try {
            emailService.sendEmailVerification(user.getEmail(), user.getFirstName(), token);
        } catch (Exception e) {
            log.error("Failed to send email verification to: {}", user.getEmail(), e);
        }
    }

    private void sendAccountLockedEmail(User user) {
        try {
            emailService.sendAccountLockedNotification(user.getEmail(), user.getFirstName());
        } catch (Exception e) {
            log.error("Failed to send account locked email to: {}", user.getEmail(), e);
        }
    }
}
