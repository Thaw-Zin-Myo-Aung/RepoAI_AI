package com.example.audit.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import java.util.Objects;

/**
 * Represents an audit log entry in the system.
 * <p>
 * This entity records actions performed by users, providing a trail for security,
 * compliance, and debugging purposes. Indexes are created on timestamp, actorId,
 * and targetUserId to optimize query performance.
 * </p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Entity
@Table(name = "audit_logs", indexes = {
        @Index(name = "idx_auditlog_timestamp", columnList = "timestamp"),
        @Index(name = "idx_auditlog_actorid", columnList = "actorId"),
        @Index(name = "idx_auditlog_targetuserid", columnList = "targetUserId")
})
public class AuditLog {

    /**
     * The unique identifier for the audit log entry.
     */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * The exact timestamp when the audited action occurred.
     */
    @Column(nullable = false)
    private LocalDateTime timestamp;

    /**
     * The ID of the user (actor) who performed the action.
     */
    @Column(nullable = false)
    private Long actorId;

    /**
     * The type of action performed (e.g., "USER_LOGIN", "DOCUMENT_DELETED").
     */
    @Column(nullable = false)
    private String actionType;

    /**
     * The ID of the user who was the target of the action.
     * This can be null if the action is not targeted at a specific user.
     */
    @Column
    private Long targetUserId;

    /**
     * Default constructor required by JPA.
     */
    public AuditLog() {
    }

    /**
     * Constructs a new AuditLog with specified details.
     *
     * @param timestamp    The time the action occurred. Cannot be null.
     * @param actorId      The ID of the user who performed the action. Cannot be null.
     * @param actionType   The type of action performed. Cannot be null.
     * @param targetUserId The ID of the user on whom the action was performed (can be null).
     */
    public AuditLog(LocalDateTime timestamp, Long actorId, String actionType, Long targetUserId) {
        this.timestamp = timestamp;
        this.actorId = actorId;
        this.actionType = actionType;
        this.targetUserId = targetUserId;
    }

    // Getters and Setters

    /**
     * Gets the unique identifier of the audit log.
     *
     * @return the ID of the audit log.
     */
    public Long getId() {
        return id;
    }

    /**
     * Sets the unique identifier of the audit log.
     *
     * @param id the ID to set.
     */
    public void setId(Long id) {
        this.id = id;
    }

    /**
     * Gets the timestamp of the action.
     *
     * @return the timestamp.
     */
    public LocalDateTime getTimestamp() {
        return timestamp;
    }

    /**
     * Sets the timestamp of the action.
     *
     * @param timestamp the timestamp to set.
     */
    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }

    /**
     * Gets the ID of the actor.
     *
     * @return the actor's ID.
     */
    public Long getActorId() {
        return actorId;
    }

    /**
     * Sets the ID of the actor.
     *
     * @param actorId the actor's ID to set.
     */
    public void setActorId(Long actorId) {
        this.actorId = actorId;
    }

    /**
     * Gets the type of action.
     *
     * @return the action type.
     */
    public String getActionType() {
        return actionType;
    }

    /**
     * Sets the type of action.
     *
     * @param actionType the action type to set.
     */
    public void setActionType(String actionType) {
        this.actionType = actionType;
    }

    /**
     * Gets the ID of the target user.
     *
     * @return the target user's ID, or null if not applicable.
     */
    public Long getTargetUserId() {
        return targetUserId;
    }

    /**
     * Sets the ID of the target user.
     *
     * @param targetUserId the target user's ID to set.
     */
    public void setTargetUserId(Long targetUserId) {
        this.targetUserId = targetUserId;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        AuditLog auditLog = (AuditLog) o;
        return Objects.equals(id, auditLog.id);
    }

    @Override
    public int hashCode() {
        return Objects.hash(id);
    }

    @Override
    public String toString() {
        return "AuditLog{" +
                "id=" + id +
                ", timestamp=" + timestamp +
                ", actorId=" + actorId +
                ", actionType='" + actionType + '\'' +
                ", targetUserId=" + targetUserId +
                '}';
    }
}
