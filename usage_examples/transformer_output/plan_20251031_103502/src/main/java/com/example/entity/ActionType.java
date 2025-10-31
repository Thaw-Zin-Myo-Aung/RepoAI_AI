package com.example.entity;

/**
 * Represents the type of action performed on an entity.
 *
 * <p>This enum is used to categorize audit logs or history records
 * based on the operation that was performed.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
public enum ActionType {

    /**
     * Represents a create action, typically when a new entity is persisted.
     */
    CREATE,

    /**
     * Represents an update action, when an existing entity is modified.
     */
    UPDATE,

    /**
     * Represents a delete action, when an entity is removed.
     */
    DELETE;
}
