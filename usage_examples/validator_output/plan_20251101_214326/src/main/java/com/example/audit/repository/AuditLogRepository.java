package com.example.audit.repository;

import com.example.audit.model.AuditLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Spring Data JPA repository for the {@link AuditLog} entity.
 *
 * <p>This interface provides the mechanism for storage, retrieval,
 * and search behavior for AuditLog entities. It leverages Spring Data JPA
 * to automatically implement repository functionality.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {
    // Spring Data JPA will automatically implement basic CRUD operations.
    // Custom query methods can be defined here if needed in the future.
}
