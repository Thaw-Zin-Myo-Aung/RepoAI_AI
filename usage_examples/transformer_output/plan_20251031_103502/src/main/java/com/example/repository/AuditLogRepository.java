package com.example.repository;

import com.example.model.AuditLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

/**
 * Spring Data JPA repository for the {@link AuditLog} entity.
 * <p>
 * This interface provides CRUD (Create, Read, Update, Delete) operations
 * for {@link AuditLog} entities, leveraging the power of Spring Data JPA.
 * No additional methods are needed for basic CRUD functionality as they are
 * inherited from {@link JpaRepository}.
 * </p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Repository
public interface AuditLogRepository extends JpaRepository<AuditLog, Long> {
}
