package com.example.audit;

/**
 * Represents the type of action performed in an audit log.
 *
 * <p>This enum is used to categorize audit events into creation,
 * update, or deletion operations.</p>
 *
 * @author RepoAI
 * @since 1.0.0
 */
public enum ActionType {

    /**
     * Represents a resource creation action.
     */
    CREATE,

    /**
     * Represents a resource update action.
     */
    UPDATE,

    /**
     * Represents a resource deletion action.
     */
    DELETE;
}
