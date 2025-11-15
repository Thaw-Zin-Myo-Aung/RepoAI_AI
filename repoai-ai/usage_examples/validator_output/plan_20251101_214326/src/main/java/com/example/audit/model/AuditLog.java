package com.example.audit.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import org.hibernate.annotations.CreationTimestamp;

import java.time.LocalDateTime;

/**
 * Represents an audit log entry in the system.
 *
 * <p>This entity records actions performed by users, such as creating or deleting
 * other users. It includes details about the actor, the action, the target,
 * and when the action occurred.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Entity
@Table(name = "audit_logs", indexes = {
    @Index(name = "idx_auditlog_actorid", columnList = "actorId"),
    @Index(name = "idx_auditlog_actiontype", columnList = "actionType"),
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
     * The timestamp when the action occurred.
     * Automatically set by Hibernate upon creation.
     */
    @CreationTimestamp
    @Column(name = "timestamp", nullable = false, updatable = false)
    private LocalDateTime timestamp;

    /**
     * The ID of the user who performed the action.
     */
    @Column(name = "actorId", nullable = false)
    private Long actorId;

    /**
     * The type of action performed (e.g., "USER_CREATED", "USER_DELETED").
     */
    @Column(name = "actionType", nullable = false, length = 50)
    private String actionType;

    /**
     * The ID of the user on whom the action was performed.
     */
    @Column(name = "targetUserId", nullable = false)
    private Long targetUserId;

    /**
     * Default constructor for JPA.
     */
    public AuditLog() {
    }

    /**
     * Constructs a new AuditLog instance.
     *
     * @param actorId      The ID of the user performing the action.
     * @param actionType   The type of action performed.
     * @param targetUserId The ID of the user being acted upon.
     */
    public AuditLog(Long actorId, String actionType, Long targetUserId) {
        this.actorId = actorId;
        this.actionType = actionType;
        this.targetUserId = targetUserId;
    }

    // Getters and Setters

    /**
     * Gets the unique identifier of the audit log.
     *
     * @return The ID.
     */
    public Long getId() {
        return id;
    }

    /**
     * Sets the unique identifier of the audit log.
     *
     * @param id The ID to set.
     */
    public void setId(Long id) {
        this.id = id;
    }

    /**
     * Gets the timestamp of the action.
     *
     * @return The timestamp.
     */
    public LocalDateTime getTimestamp() {
        return timestamp;
    }

    /**
     * Sets the timestamp of the action.
     *
     * @param timestamp The timestamp to set.
     */
    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }

    /**
     * Gets the ID of the actor.
     *
     * @return The actor's ID.
     */
    public Long getActorId() {
        return actorId;
    }

    /**
     * Sets the ID of the actor.
     *
     * @param actorId The actor's ID to set.
     */
    public void setActorId(Long actorId) {
        this.actorId = actorId;
    }

    /**
     * Gets the type of action.
     *
     * @return The action type.
     */
    public String getActionType() {
        return actionType;
    }

    /**
     * Sets the type of action.
     *
     * @param actionType The action type to set.
     */
    public void setActionType(String actionType) {
        this.actionType = actionType;
    }

    /**
     * Gets the ID of the target user.
     *
     * @return The target user's ID.
     */
    public Long getTargetUserId() {
        return targetUserId;
    }

    /**
     * Sets the ID of the target user.
     *
     * @param targetUserId The target user's ID to set.
     */
    public void setTargetUserId(Long targetUserId) {
        this.targetUserId = targetUserId;
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
