# Transformer Agent Improvements: Maven Dependency Management

## Problem Identified

During integration testing, we discovered that the Transformer Agent adds Spring annotations (like `@Service`) to Java code without adding the required Spring dependencies to `pom.xml`. This causes compilation failures:

```
WARNING: Compilation has 4 errors:
   /tmp/.../UserService.java:3 - package org.springframework.stereotype does not exist
   /tmp/.../UserService.java:13 - cannot find symbol
```

## Root Cause

The Transformer Agent has **no tool** for Maven dependency management. Current tools:
- ✅ `generate_class_template` - Creates Java class boilerplate
- ✅ `extract_imports` - Parses import statements
- ✅ `extract_method_signatures` - Extracts method signatures  
- ✅ `extract_annotations` - Extracts annotations
- ✅ `generate_diff` - Creates unified diffs
- ✅ `count_diff_lines` - Counts diff statistics
- ✅ `get_file_context` - Reads file contents
- ❌ **Missing**: Maven/Gradle dependency management

## Solution: Add Maven Utilities

### 1. Created `src/repoai/utils/maven_utils.py`

New utilities for Maven pom.xml manipulation:

```python
# Core Functions
def parse_pom_xml(pom_path) -> ElementTree
def get_dependencies(pom_path) -> list[dict[str, str]]
def dependency_exists(pom_path, group_id, artifact_id) -> bool
def add_dependency(pom_path, group_id, artifact_id, version, scope=None) -> bool
def format_pom_xml(pom_path) -> None
def get_common_dependencies() -> dict[str, dict[str, str]]
```

**Features:**
- ✅ Parse and modify pom.xml safely
- ✅ Check if dependency already exists (avoid duplicates)
- ✅ Add new dependencies with proper XML structure
- ✅ Support scope (compile, test, provided, runtime)
- ✅ Common dependencies with stable versions (Spring Boot, JUnit, etc.)

### 2. Next Steps to Integrate

#### Option A: Add Tool to Transformer Agent (Recommended)

```python
# In src/repoai/agents/transformer_agent.py

from repoai.utils.maven_utils import add_dependency, get_common_dependencies

@agent.tool
def add_maven_dependency(
    ctx: RunContext[TransformerDependencies],
    dependency_key: str,
) -> dict[str, str]:
    """
    Add a Maven dependency to pom.xml.
    
    Args:
        dependency_key: Common dependency name (e.g., "spring-boot-starter-web")
                       or "groupId:artifactId:version" format
    
    Returns:
        Dict with status and details
    
    Example:
        # Add Spring Web
        add_maven_dependency("spring-boot-starter-web")
        
        # Add custom dependency
        add_maven_dependency("com.google.guava:guava:32.1.3-jre")
    """
    repo_path = ctx.deps.repository_path
    if not repo_path:
        return {"success": False, "error": "Repository path not set"}
    
    pom_path = Path(repo_path) / "pom.xml"
    
    # Check if it's a common dependency
    common_deps = get_common_dependencies()
    if dependency_key in common_deps:
        dep = common_deps[dependency_key]
        success = add_dependency(
            pom_path,
            dep["groupId"],
            dep["artifactId"],
            dep["version"],
            dep.get("scope"),
        )
        return {
            "success": success,
            "groupId": dep["groupId"],
            "artifactId": dep["artifactId"],
            "version": dep["version"],
        }
    
    # Parse custom format: groupId:artifactId:version
    try:
        parts = dependency_key.split(":")
        if len(parts) != 3:
            return {"success": False, "error": "Invalid format. Use groupId:artifactId:version"}
        
        group_id, artifact_id, version = parts
        success = add_dependency(pom_path, group_id, artifact_id, version)
        return {
            "success": success,
            "groupId": group_id,
            "artifactId": artifact_id,
            "version": version,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
```

#### Option B: Add to System Prompt

Update transformer's system prompt to mention dependency management:

```python
TRANSFORMER_INSTRUCTIONS += """

**Maven Dependency Management:**

When adding annotations or using libraries, ALWAYS add required dependencies:

1. For Spring annotations (@Service, @Component, @Autowired, etc.):
   - Use `add_maven_dependency("spring-context")` for @Service, @Component
   - Use `add_maven_dependency("spring-boot-starter-web")` for Spring Boot web
   
2. For testing annotations (@Test, @Mock, etc.):
   - Use `add_maven_dependency("junit-jupiter")` for JUnit 5
   - Use `add_maven_dependency("mockito-core")` for Mockito

3. For Lombok (@Data, @Getter, @Setter, etc.):
   - Use `add_maven_dependency("lombok")`

**Available Common Dependencies:**
- spring-boot-starter-web
- spring-boot-starter-data-jpa
- spring-boot-starter-security
- spring-boot-starter-test
- spring-context
- junit-jupiter
- mockito-core
- lombok
- slf4j-api
- logback-classic

**Example:**
```java
// Step 1: Add Spring dependency
add_maven_dependency("spring-context")

// Step 2: Add annotation
import org.springframework.stereotype.Service;

@Service
public class UserService {
    // ...
}
```
"""
```

#### Option C: Validator Feedback Loop (Current Behavior)

Keep current approach where Validator detects missing dependencies and suggests fixes. This already works but requires retry cycles.

## Recommended Approach

**Implement Option A + B:**
1. Add `add_maven_dependency` tool to Transformer Agent
2. Update system prompt with dependency guidelines
3. Keep Validator feedback as safety net

This gives the LLM:
- ✅ **Proactive**: Can add dependencies while transforming
- ✅ **Smart**: Knows common dependency mappings
- ✅ **Safe**: Validator still catches mistakes
- ✅ **Efficient**: Reduces retry cycles

## Benefits

1. **Fewer Compilation Errors**: Dependencies added upfront
2. **Faster Pipeline**: Less back-and-forth with Validator
3. **Better Code Quality**: Complete, buildable changes
4. **Smarter Agent**: Understands Java ecosystem dependencies

## Implementation Priority

- **High Priority**: Add tool to Transformer (Option A) - enables core functionality
- **Medium Priority**: Update prompts (Option B) - improves guidance
- **Done**: Maven utilities created ✅
- **Future**: Gradle support (similar pattern)

## Testing

The integration test already validates this flow:
```bash
uv run pytest tests/integration/test_full_pipeline.py -v -s
```

After adding the tool, the test should show:
- ✅ Transformer adds Spring annotation
- ✅ Transformer adds Spring dependency to pom.xml
- ✅ Compilation succeeds without errors
- ✅ Validation passes

## Files Changed

1. ✅ Created: `src/repoai/utils/maven_utils.py` (356 lines)
2. 🔄 TODO: Update `src/repoai/agents/transformer_agent.py` (add tool)
3. 🔄 TODO: Update `src/repoai/agents/prompts.py` (add guidelines)

---

**Status**: Maven utilities ready ✅  
**Next**: Integrate tool into Transformer Agent  
**Impact**: Eliminates dependency-related compilation errors  
