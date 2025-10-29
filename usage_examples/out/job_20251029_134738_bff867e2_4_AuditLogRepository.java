package com.example.audit.repository;

import com.example.audit.model.AuditLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Spring Data JPA repository for the {@link AuditLog} entity.
 *
 * <p>This interface provides the mechanism for storage, retrieval, and search behavior
 * for AuditLog entities. Spring Data JPA will automatically implement this repository
 * interface in a bean that has the same name (with a change in the case - it will be called
 * auditLogRepository).</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {
    // Spring Data JPA will automatically provide the implementation for CRUD operations.
    // Custom query methods can be added here if needed.
}
