"""
Abstract Syntax Tree (AST) representations
Java AST Parser for targeted context extraction.

Uses Javalang to parse Java files and extract only relavant context for large files (2000+ Lines) to avoid token limit issues.
"""

# mypy: warn-unused-ignores=False

from __future__ import annotations

from dataclasses import dataclass

import javalang

from repoai.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class JavaClass:
    """Represents a parsed Java Class Structure."""

    name: str
    package: str
    imports: list[str]
    annotations: list[str]
    extends: str | None
    implements: list[str]
    methods: list[JavaMethod]
    fields: list[JavaField]
    inner_classes: list[str]
    is_interface: bool = False
    is_enum: bool = False
    is_abstract: bool = False


@dataclass
class JavaMethod:
    """Represents a Java Method."""

    name: str
    return_type: str
    parameters: list[tuple[str, str]]  # List of (type, name)
    annotations: list[str]
    is_public: bool
    is_private: bool
    is_protected: bool
    is_static: bool
    throws: list[str]
    body: str | None = None  # Method body as string (if available)


@dataclass
class JavaField:
    """Represents a Java Field."""

    name: str
    type: str
    annotations: list[str]
    is_public: bool
    is_private: bool
    is_static: bool
    is_final: bool


def parse_java_file(code: str) -> JavaClass | None:
    """
    Parse Java code into structured AST representation.

    Args:
        code: Java Source code

    Returns:
        JavaClass object or None if parsing fails.

    Example:
        java_class = parse_java_file(code)
        print(f"Class: {java_class.name}")
        print(f"Methods: {len(java_class.methods)}")
    """
    try:
        tree = javalang.parse.parse(code)

        # Extract package (tree.package is always available, can be None)
        package = tree.package.name if tree.package else ""  # type: ignore

        # Extract imports (tree.imports is always a list, can be empty)
        imports = [imp.path for imp in tree.imports]  # type: ignore

        # Find the primary class/interface (tree.types is always a list)
        classes = list(tree.types)  # type: ignore
        if not classes:
            logger.warning("No class found in Java File.")
            return None

        primary_class = classes[0]  # Take first class (Main class)

        # Extract class info
        class_name = primary_class.name
        annotations = (
            [ann.name for ann in primary_class.annotations] if primary_class.annotations else []
        )

        # Check class type
        is_interface = isinstance(primary_class, javalang.tree.InterfaceDeclaration)  # type: ignore
        is_enum = isinstance(primary_class, javalang.tree.EnumDeclaration)  # type: ignore

        # Extract extends/implements (always exist, can be None or empty list)
        extends = primary_class.extends.name if primary_class.extends else None  # type: ignore
        implements = (
            [impl.name for impl in primary_class.implements]  # type: ignore
            if primary_class.implements  # type: ignore
            else []
        )

        # Extract methods (always exists as attribute)
        methods = []
        for method in primary_class.methods:  # type: ignore
            method_obj = JavaMethod(
                name=method.name,
                return_type=method.return_type.name if method.return_type else "void",
                parameters=(
                    [(param.type.name, param.name) for param in method.parameters]
                    if method.parameters
                    else []
                ),
                annotations=[ann.name for ann in method.annotations] if method.annotations else [],
                is_public="public" in method.modifiers if method.modifiers else False,  # type: ignore
                is_private="private" in method.modifiers if method.modifiers else False,
                is_protected="protected" in method.modifiers if method.modifiers else False,
                is_static="static" in method.modifiers if method.modifiers else False,
                throws=list(method.throws) if method.throws else [],
            )
            methods.append(method_obj)

        # Extract fields (always exists as attribute)
        fields = []
        for field_decl in primary_class.fields:  # type: ignore
            for declator in field_decl.declarators:
                field_obj = JavaField(
                    name=declator.name,
                    type=field_decl.type.name if field_decl.type else "Unknown",
                    annotations=(
                        [ann.name for ann in field_decl.annotations]
                        if field_decl.annotations
                        else []
                    ),
                    is_public="public" in field_decl.modifiers if field_decl.modifiers else False,
                    is_private="private" in field_decl.modifiers if field_decl.modifiers else False,
                    is_static="static" in field_decl.modifiers if field_decl.modifiers else False,
                    is_final="final" in field_decl.modifiers if field_decl.modifiers else False,
                )
                fields.append(field_obj)

        # Extract inner classes (body always exists as attribute)
        inner_classes = []
        if primary_class.body:  # type: ignore
            for member in primary_class.body:  # type: ignore
                if isinstance(
                    member,
                    javalang.tree.ClassDeclaration
                    | javalang.tree.InterfaceDeclaration
                    | javalang.tree.EnumDeclaration,
                ):  # type: ignore
                    inner_classes.append(member.name)

        java_class = JavaClass(
            name=class_name,
            package=package,
            imports=imports,
            annotations=annotations,
            extends=extends,
            implements=implements,
            methods=methods,
            fields=fields,
            inner_classes=inner_classes,
            is_interface=is_interface,
            is_enum=is_enum,
            is_abstract="abstract" in primary_class.modifiers if primary_class.modifiers else False,
        )

        logger.debug(
            f"Parsed Java class: {java_class.name}, "
            f"methods={len(methods)}, fields={len(fields)}, inner_classes={len(inner_classes)}"
        )
        return java_class

    except javalang.parser.JavaSyntaxError as e:
        logger.error(f"Java syntax error: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to parse Java File: {e}")
        return None


def extract_relevant_context(code: str, intent: str, max_tokens: int = 2000) -> str:
    """
    Extract only relevant context from large Java Files.

    For files > 2000 lines, this extracts:
    - Package and imports
    - Class structure
    - Relevant methods based on intent
    - Annotations

    Args:
        code: Full Java source code
        intent: Refactoring intent (e.g., "add_jwt_authentication")
        max_tokens: Maximum tokens to return (approximate)

    Returns:
        str: Extracted relevant context

    Example:
        context = extract_relevant_context(large_code, "add_jwt_auth")
        # Returns only auth-related methods, not entire 3000-line file
    """
    lines = code.split("\n")
    line_count = len(lines)

    # Small files: return full content
    if line_count < 500:
        logger.debug(f"Small file ({line_count} lines), returning full content")
        return code

    # Medium files: try AST extraction
    if line_count < 2000:
        logger.debug(f"Medium file ({line_count} lines), attempting AST extraction")
        java_class = parse_java_file(code)
        if java_class:
            return _build_targeted_context(java_class, intent)
        else:
            # Fallback: return full content
            return code

    # Large files: mandatory AST extraction
    logger.info(f"Large file ({line_count} lines), using targeted AST extraction")
    java_class = parse_java_file(code)
    if not java_class:
        # If AST parsing fails, return truncated version
        logger.warning("AST parsing failed, returning truncated content")
        return _truncate_code(code, max_tokens)

    return _build_targeted_context(java_class, intent, max_tokens)


def _build_targeted_context(java_class: JavaClass, intent: str, max_tokens: int = 2000) -> str:
    """
    Build targeted context from parsed Java Class.

    Includes only methods and fields relevant to the intent.
    """
    intent_lower = intent.lower()
    context_lines = []

    # Package
    if java_class.package:
        context_lines.append(f"package {java_class.package};\n")
        context_lines.append("")

    # Imports (relevant ones only)
    relevant_imports = _filter_relevant_imports(java_class.imports, intent_lower)
    for imp in relevant_imports[:20]:  # Limit to 20 imports
        context_lines.append(imp)

    if relevant_imports:
        context_lines.append("")

    # Class declaration
    class_type = (
        "interface" if java_class.is_interface else "enum" if java_class.is_enum else "class"
    )
    annotations_str = "\n".join(f"@{ann}" for ann in java_class.annotations)
    if annotations_str:
        context_lines.append(annotations_str)

    class_decl = f"public {class_type} {java_class.name}"
    if java_class.extends:
        class_decl += f" extends {java_class.extends}"
    if java_class.implements:
        class_decl += f" implements {', '.join(java_class.implements)}"
    context_lines.append(class_decl + " {")
    context_lines.append("")

    # Fields (relevant ones only)
    relevant_fields = _filter_relevant_fields(java_class.fields, intent_lower)
    for field in relevant_fields[:10]:  # Limit to 10 fields
        field_str = _format_field(field)
        context_lines.append(f"    {field_str}")

    if relevant_fields:
        context_lines.append("")

    # Methods (relevant ones only)
    relevant_methods = _filter_relevant_methods(java_class.methods, intent_lower)
    for method in relevant_methods[:15]:  # Limit to 15 methods
        method_str = _format_method_signature(method)
        context_lines.append(f"    {method_str}")
        context_lines.append("")

    # Note about omitted content
    omitted_methods = len(java_class.methods) - len(relevant_methods)
    if omitted_methods > 0:
        context_lines.append(f"    // ... {omitted_methods} other methods omitted for brevity")

    context_lines.append("}")

    context = "\n".join(context_lines)

    # Estimate tokens (rough: 1 token ≈ 4 characters)
    estimated_tokens = len(context) // 4
    logger.debug(
        f"Built targeted context: {len(context)} chars, "
        f"~{estimated_tokens} tokens, "
        f"{len(relevant_methods)}/{len(java_class.methods)} methods"
    )

    return context


def _filter_relevant_imports(imports: list[str], intent: str) -> list[str]:
    """Filter imports relevant to the intent."""
    # Keywords to look for based on intent
    keywords = _get_intent_keywords(intent)

    relevant = []
    for imp in imports:
        imp_lower = imp.lower()
        # Always include common imports
        if any(common in imp_lower for common in ["java.util", "java.io", "java.lang"]):
            relevant.append(imp)
        # Include intent-related imports
        elif any(keyword in imp_lower for keyword in keywords):
            relevant.append(imp)
        # Include Spring/JPA imports
        elif any(
            framework in imp_lower for framework in ["spring", "jakarta", "javax", "hibernate"]
        ):
            relevant.append(imp)

    return relevant


def _filter_relevant_methods(methods: list[JavaMethod], intent: str) -> list[JavaMethod]:
    """Filter methods relevant to the intent."""
    keywords = _get_intent_keywords(intent)

    relevant = []
    for method in methods:
        method_name_lower = method.name.lower()

        # Include if method name matches intent keywords
        if any(keyword in method_name_lower for keyword in keywords):
            relevant.append(method)
        # Include if has relevant annotations
        elif any(keyword in ann.lower() for ann in method.annotations for keyword in keywords):
            relevant.append(method)
        # Include public methods (likely API)
        elif method.is_public:
            relevant.append(method)

    return relevant


def _filter_relevant_fields(fields: list[JavaField], intent: str) -> list[JavaField]:
    """Filter fields relevant to the intent."""
    keywords = _get_intent_keywords(intent)

    relevant = []
    for field in fields:
        field_name_lower = field.name.lower()

        # Include if field name matches intent keywords
        if any(keyword in field_name_lower for keyword in keywords):
            relevant.append(field)
        # Include if has relevant annotations
        elif any(keyword in ann.lower() for ann in field.annotations for keyword in keywords):
            relevant.append(field)
        # Include injected dependencies
        elif any(ann in field.annotations for ann in ["Autowired", "Inject", "Value"]):
            relevant.append(field)

    return relevant


def _get_intent_keywords(intent: str) -> list[str]:
    """Extract keywords from intent string."""
    # Common keywords by intent type
    keyword_map = {
        "auth": ["auth", "login", "token", "jwt", "password", "user", "security"],
        "jwt": ["jwt", "token", "auth", "claim", "sign", "validate"],
        "oauth": ["oauth", "auth", "client", "token", "scope"],
        "database": ["repository", "entity", "query", "database", "jpa", "sql"],
        "rest": ["rest", "controller", "endpoint", "api", "request", "response"],
        "service": ["service", "business", "logic", "transaction"],
        "config": ["config", "bean", "property", "setting"],
        "test": ["test", "mock", "assert", "verify"],
    }

    intent_lower = intent.lower()
    keywords = set()

    # Add intent-specific keywords
    for key, words in keyword_map.items():
        if key in intent_lower:
            keywords.update(words)

    # Add words from intent itself
    intent_words = intent_lower.replace("_", " ").split()
    keywords.update(intent_words)

    return list(keywords)


def _format_field(field: JavaField) -> str:
    """Format field as Java code."""
    parts = []

    # Annotations
    if field.annotations:
        parts.append(" ".join(f"@{ann}" for ann in field.annotations) + " ")

    # Modifiers
    if field.is_public:
        parts.append("public ")
    elif field.is_private:
        parts.append("private ")

    if field.is_static:
        parts.append("static ")
    if field.is_final:
        parts.append("final ")

    # Type and name
    parts.append(f"{field.type} {field.name};")

    return "".join(parts)


def _format_method_signature(method: JavaMethod) -> str:
    """Format method signature as Java code."""
    parts = []

    # Annotations
    if method.annotations:
        ann_str = "\n    ".join(f"@{ann}" for ann in method.annotations)
        parts.append(ann_str + "\n    ")

    # Modifiers
    if method.is_public:
        parts.append("public ")
    elif method.is_private:
        parts.append("private ")
    elif method.is_protected:
        parts.append("protected ")

    if method.is_static:
        parts.append("static ")

    # Return type and name
    parts.append(f"{method.return_type} {method.name}(")

    # Parameters
    if method.parameters:
        params = ", ".join(f"{ptype} {pname}" for ptype, pname in method.parameters)
        parts.append(params)

    parts.append(")")

    # Throws
    if method.throws:
        parts.append(f" throws {', '.join(method.throws)}")

    parts.append(" { /* ... */ }")

    return "".join(parts)


def _truncate_code(code: str, max_tokens: int) -> str:
    """
    Truncate code to approximate token limit as fallback.
    """
    # Rough estimate: 1 token ≈ 4 characters
    max_chars = max_tokens * 4

    if len(code) <= max_chars:
        return code

    truncated = code[:max_chars]
    truncated += "\n\n// ... (file truncated due to size)"

    logger.warning(f"Code truncated from {len(code)} to {len(truncated)} characters")
    return truncated
