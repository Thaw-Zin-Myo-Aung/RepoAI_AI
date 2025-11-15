# Build System Policy

## Overview

RepoAI uses **Maven as the primary build system** for Java enterprise applications. Gradle is supported but only when explicitly detected in existing projects.

## Rationale

- **Maven is the industry standard** for enterprise Java development
- Spring Boot documentation and most examples use Maven
- Maven has better corporate adoption and tooling support
- Simplifies testing by focusing on one primary build system

## Implementation

### Default Behavior

When generating or refactoring Java projects:
1. **Default to Maven** (create `pom.xml`) unless Gradle is detected
2. Only use Gradle if `build.gradle` or `build.gradle.kts` exists in the project
3. All dependency management assumes Maven format (groupId:artifactId:version)

### Code Changes

The following files have been updated to reflect this policy:

#### 1. `src/repoai/utils/file_writer.py`
- Module docstring updated to clarify Maven is default, Gradle only when detected
- `write_code_changes()` method documentation updated
- `_create_build_config()` now explicitly states "Maven build configuration (default)"
- `_generate_minimal_pom()` clarified as generating Maven format

#### 2. `src/repoai/agents/prompts/intake_prompts.py`
- **Java Build System Detection** section updated:
  - "**Default to Maven** if not specified (primary build system for enterprise Java)"
  - "Only use Gradle if build.gradle is explicitly present in the project"

#### 3. `src/repoai/agents/prompts/planner_prompts.py`
- **Java Ecosystem Expertise** section updated: "Build systems: Maven (primary/default) and Gradle (when detected)"
- `add_dependency` operation clarified: "Add Maven dependency to pom.xml (primary) or Gradle if build.gradle exists"
- **Step Ordering Rules** updated: "Add Maven dependencies (pom.xml) before using them in code"

## Testing Focus

### Primary Testing: Maven
- All standard tests use Maven projects
- Generated examples use Maven by default
- Integration tests assume Maven build structure

### Secondary Testing: Gradle
- Gradle tests only run when:
  - Project explicitly has `build.gradle` or `build.gradle.kts`
  - Testing framework detection specifically looks for Gradle files
  - User explicitly requests Gradle support

## Usage Examples

### Generated Project Structure (Default)
```
project/
├── src/
│   ├── main/java/...
│   └── test/java/...
└── pom.xml          # Maven default
```

### Detected Gradle Project
```
project/
├── src/
│   ├── main/java/...
│   └── test/java/...
├── build.gradle     # Detected - use Gradle
└── settings.gradle
```

## Dependencies

When dependencies are added:
- **Format**: Maven coordinate format `groupId:artifactId:version`
- **File**: Added to `pom.xml` by default
- **Gradle projects**: Converted to Gradle format only if `build.gradle` detected

## Migration Path

For existing Gradle projects:
1. RepoAI will detect `build.gradle` in the repository
2. Continue using Gradle for that project
3. No automatic conversion from Gradle to Maven

## Future Considerations

- May add explicit `--build-system gradle` flag for user override
- Consider adding Gradle → Maven migration tool
- Document Gradle-specific features if needed

## Last Updated

January 27, 2025 - Initial policy documentation
