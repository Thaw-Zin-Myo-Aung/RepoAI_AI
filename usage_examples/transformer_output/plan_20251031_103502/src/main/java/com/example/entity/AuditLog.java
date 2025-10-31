package com.example.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/**
 * Represents an audit log entry in the system.
 *
 * <p>This entity is used to record significant events that occur within the application,
 * such as user actions, system events, or important state changes. Each log entry
 * captures what happened, who did it, and when it occurred.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
@Entity
@Table(name = "audit_logs", indexes = {
    @Index(name = "idx_auditlog_event_type", columnList = "event_type"),
    @Index(name = "idx_auditlog_timestamp", columnList = "timestamp"),
    @Index(name = "idx_auditlog_actor", columnList = "actor")
})
public class AuditLog {

    /**
     * The unique identifier for the audit log entry.
     */
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    /**
     * The type of event that was logged (e.g., "USER_CREATED", "DOCUMENT_DELETED").
     */
    @Column(name = "event_type", nullable = false, length = 50)
    private String eventType;

    /**
     * The identifier of the user or system component that performed the action.
     */
    @Column(name = "actor", nullable = false)
    private String actor;

    /**
     * The entity or resource that was affected by the event (e.g., "User", "Order").
     */
    @Column(name = "target_entity", length = 100)
    private String targetEntity;

    /**
     * The unique identifier of the affected entity or resource.
     */
    @Column(name = "target_id")
    private String targetId;

    /**
     * The timestamp indicating when the event occurred.
     */
    @Column(name = "timestamp", nullable = false)
    private LocalDateTime timestamp;

    /**
     * A detailed description of the event, which can include old and new values,
     * often stored in a structured format like JSON.
     */
    @Column(name = "details", columnDefinition = "TEXT")
    private String details;

    /**
     * Default constructor required by JPA.
     */
    public AuditLog() {
    }

    /**
     * Constructs a new AuditLog with specified details.
     *
     * @param eventType    The type of event.
     * @param actor        The actor who performed the action.
     * @param targetEntity The entity affected.
     * @param targetId     The ID of the affected entity.
     * @param timestamp    The time the event occurred.
     * @param details      Detailed information about the event.
     */
    public AuditLog(String eventType, String actor, String targetEntity, String targetId, LocalDateTime timestamp, String details) {
        this.eventType = eventType;
        this.actor = actor;
        this.targetEntity = targetEntity;
        this.targetId = targetId;
        this.timestamp = timestamp;
        this.details = details;
    }

    // Getters and Setters

    /**
     * Gets the unique identifier of the audit log.
     *
     * @return The ID of the log entry.
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
     * Gets the type of the event.
     *
     * @return The event type.
     */
    public String getEventType() {
        return eventType;
    }

    /**
     * Sets the type of the event.
     *
     * @param eventType The event type to set.
     */
    public void setEventType(String eventType) {
        this.eventType = eventType;
    }

    /**
     * Gets the actor who performed the action.
     *
     * @return The actor's identifier.
     */
    public String getActor() {
        return actor;
    }

    /**
     * Sets the actor who performed the action.
     *
     * @param actor The actor's identifier to set.
     */
    public void setActor(String actor) {
        this.actor = actor;
    }

    /**
     * Gets the target entity affected by the event.
     *
     * @return The name of the target entity.
     */
    public String getTargetEntity() {
        return targetEntity;
    }

    /**
     * Sets the target entity affected by the event.
     *
     * @param targetEntity The name of the target entity to set.
     */
    public void setTargetEntity(String targetEntity) {
        this.targetEntity = targetEntity;
    }

    /**
     * Gets the ID of the target entity.
     *
     * @return The ID of the target entity.
     */
    public String getTargetId() {
        return targetId;
    }

    /**
     * Sets the ID of the target entity.
     *
     * @param targetId The ID of the target entity to set.
     */
    public void setTargetId(String targetId) {
        this.targetId = targetId;
    }

    /**
     * Gets the timestamp of the event.
     *
     * @return The event timestamp.
     */
    public LocalDateTime getTimestamp() {
        return timestamp;
    }

    /**
     * Sets the timestamp of the event.
     *
     * @param timestamp The event timestamp to set.
     */
    public void setTimestamp(LocalDateTime timestamp) {
        this.timestamp = timestamp;
    }

    /**
     * Gets the detailed description of the event.
     *
     * @return The event details.
     */
    public String getDetails() {
        return details;
    }

    /**
     * Sets the detailed description of the event.
     *
     * @param details The event details to set.
     */
    public void setDetails(String details) {
        this.details = details;
    }
}
