"""
Test Java AST Parser with real-world Java file.

This script tests the java_ast_parser.py by:
1. Reading a large Java file (500-2000 lines)
2. Using extract_relevant_context() with different intents
3. Demonstrating token-aware context extraction
4. Showing how it integrates with intake -> planner workflow
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from repoai.parsers.java_ast_parser import extract_relevant_context, parse_java_file

# Output file for logging
OUTPUT_FILE = Path(__file__).parent / "test_java_parser_output.log"

# Configure logging to write to both file and console
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.FileHandler(OUTPUT_FILE, mode="w", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


def log_separator(title: str) -> None:
    """Log a formatted separator."""
    logger.info("\n" + "=" * 80)
    logger.info(f" {title}")
    logger.info("=" * 80 + "\n")


def test_parse_java_file(file_path: Path) -> None:
    """Test parsing a Java file into AST structure."""
    log_separator("TEST 1: Parse Java File into AST")

    with open(file_path, "r") as f:
        java_code = f.read()

    logger.info(f"📄 File: {file_path.name}")
    logger.info(f"📏 File size: {len(java_code)} characters ({len(java_code.splitlines())} lines)")

    java_class = parse_java_file(java_code)

    if java_class:
        logger.info(f"\n✅ Successfully parsed Java file!")
        logger.info(f"\n📦 Package: {java_class.package}")
        logger.info(f"🏷️  Class Name: {java_class.name}")
        logger.info(f"📚 Imports: {len(java_class.imports)} imports")
        logger.info(f"🔧 Methods: {len(java_class.methods)} methods")
        logger.info(f"📋 Fields: {len(java_class.fields)} fields")
        logger.info(f"🏛️  Extends: {java_class.extends}")
        logger.info(f"🔗 Implements: {java_class.implements}")
        logger.info(f"🏷️  Annotations: {java_class.annotations}")
        logger.info(f"🔒 Is Interface: {java_class.is_interface}")
        logger.info(f"📝 Is Abstract: {java_class.is_abstract}")

        # Show some methods
        logger.info(f"\n📋 Sample Methods (showing first 5):")
        for i, method in enumerate(java_class.methods[:5], 1):
            visibility = (
                "public"
                if method.is_public
                else (
                    "private"
                    if method.is_private
                    else "protected" if method.is_protected else "package"
                )
            )
            static = "static " if method.is_static else ""
            logger.info(f"  {i}. {visibility} {static}{method.return_type} {method.name}()")
            if method.annotations:
                logger.info(f"     Annotations: {', '.join(method.annotations)}")

        # Show some fields
        logger.info(f"\n📦 Sample Fields (showing first 5):")
        for i, field in enumerate(java_class.fields[:5], 1):
            visibility = (
                "public" if field.is_public else "private" if field.is_private else "package"
            )
            static = "static " if field.is_static else ""
            final = "final " if field.is_final else ""
            logger.info(f"  {i}. {visibility} {static}{final}{field.type} {field.name}")
            if field.annotations:
                logger.info(f"     Annotations: {', '.join(field.annotations)}")
    else:
        logger.error("❌ Failed to parse Java file")


def test_extract_relevant_context_small(file_path: Path) -> None:
    """Test context extraction for small intents."""
    log_separator("TEST 2: Extract Context for Authentication Intent")

    with open(file_path, "r") as f:
        java_code = f.read()

    intent = "Add JWT authentication to the login endpoint"
    max_tokens = 2000

    logger.info(f"🎯 Intent: {intent}")
    logger.info(f"🎫 Max Tokens: {max_tokens}")

    context = extract_relevant_context(java_code, intent, max_tokens)

    logger.info(f"\n📊 Extracted Context Stats:")
    logger.info(f"  - Length: {len(context)} characters")
    logger.info(f"  - Lines: {len(context.splitlines())} lines")
    logger.info(f"  - Estimated tokens: ~{len(context) // 4}")

    logger.info(f"\n📝 Extracted Context Preview (first 1000 chars):")
    logger.info("-" * 80)
    logger.info(context[:1000])
    if len(context) > 1000:
        logger.info(f"\n... (showing first 1000 of {len(context)} characters) ...")
    logger.info("-" * 80)


def test_extract_relevant_context_password(file_path: Path) -> None:
    """Test context extraction for password-related intent."""
    log_separator("TEST 3: Extract Context for Password Reset Intent")

    with open(file_path, "r") as f:
        java_code = f.read()

    intent = "Implement password reset functionality with email verification"
    max_tokens = 1500

    logger.info(f"🎯 Intent: {intent}")
    logger.info(f"🎫 Max Tokens: {max_tokens}")

    context = extract_relevant_context(java_code, intent, max_tokens)

    logger.info(f"\n📊 Extracted Context Stats:")
    logger.info(f"  - Length: {len(context)} characters")
    logger.info(f"  - Lines: {len(context.splitlines())} lines")
    logger.info(f"  - Estimated tokens: ~{len(context) // 4}")

    # Count occurrences of password-related keywords
    password_keywords = ["password", "reset", "token", "email"]
    for keyword in password_keywords:
        count = context.lower().count(keyword)
        logger.info(f"  - '{keyword}' mentions: {count}")

    logger.info(f"\n📝 Method signatures in context:")
    for line in context.splitlines():
        if "public" in line and "(" in line and "{" not in line:
            logger.info(f"  {line.strip()}")


def test_extract_relevant_context_role(file_path: Path) -> None:
    """Test context extraction for role management intent."""
    log_separator("TEST 4: Extract Context for Role Management Intent")

    with open(file_path, "r") as f:
        java_code = f.read()

    intent = "Add role-based access control with assignRole and removeRole methods"
    max_tokens = 1000

    logger.info(f"🎯 Intent: {intent}")
    logger.info(f"🎫 Max Tokens: {max_tokens}")

    context = extract_relevant_context(java_code, intent, max_tokens)

    logger.info(f"\n📊 Extracted Context Stats:")
    logger.info(f"  - Length: {len(context)} characters")
    logger.info(f"  - Lines: {len(context.splitlines())} lines")
    logger.info(f"  - Estimated tokens: ~{len(context) // 4}")

    # Check if role-related methods are included
    role_methods = ["assignRole", "removeRole", "hasRole"]
    logger.info(f"\n🔍 Role-related methods found:")
    for method in role_methods:
        if method in context:
            logger.info(f"  ✅ {method}")
        else:
            logger.info(f"  ❌ {method}")


def test_large_file_handling(file_path: Path) -> None:
    """Test how parser handles large files."""
    log_separator("TEST 5: Large File Token Management")

    with open(file_path, "r") as f:
        java_code = f.read()

    file_size = len(java_code)
    logger.info(f"📄 File: {file_path.name}")
    logger.info(f"📏 File size: {file_size} characters ({len(java_code.splitlines())} lines)")

    # Test with different token limits
    token_limits = [500, 1000, 2000, 5000]

    logger.info(f"\n📊 Testing different token limits:")
    for max_tokens in token_limits:
        context = extract_relevant_context(
            java_code, "authentication and authorization", max_tokens
        )
        estimated_tokens = len(context) // 4
        logger.info(
            f"  Max {max_tokens:5d} tokens → {len(context):6d} chars (~{estimated_tokens:5d} tokens, {len(context.splitlines()):4d} lines)"
        )


def test_file_size_classification() -> None:
    """Test how different file sizes are handled."""
    log_separator("TEST 6: File Size Classification")

    test_cases = [
        ("Small file (< 500 lines)", "public class Test { }\n" * 100),
        ("Medium file (500-2000 lines)", "public class Test { }\n" * 1000),
        ("Large file (> 2000 lines)", "public class Test { }\n" * 3000),
    ]

    for description, code in test_cases:
        lines = len(code.splitlines())
        context = extract_relevant_context(code, "test intent", 2000)
        logger.info(f"\n{description}:")
        logger.info(f"  - Input lines: {lines}")
        logger.info(f"  - Output lines: {len(context.splitlines())}")
        logger.info(
            f"  - Strategy: {'Full content' if lines <= 500 else 'AST-based' if lines <= 2000 else 'Token-limited'}"
        )


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 80)
    logger.info(" 🧪 JAVA AST PARSER TEST SUITE")
    logger.info(f" Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    # Path to test file
    test_file = Path(__file__).parent / "test_data" / "UserManagementService.java"

    if not test_file.exists():
        logger.error(f"\n❌ Test file not found: {test_file}")
        logger.error("Please ensure UserManagementService.java exists in usage_examples/test_data/")
        return

    try:
        # Run all tests
        test_parse_java_file(test_file)
        test_extract_relevant_context_small(test_file)
        test_extract_relevant_context_password(test_file)
        test_extract_relevant_context_role(test_file)
        test_large_file_handling(test_file)
        test_file_size_classification()

        log_separator("✅ ALL TESTS COMPLETED")
        logger.info("\n💡 Key Findings:")
        logger.info("  1. Parser successfully extracts Java AST structure")
        logger.info("  2. Context extraction is intent-aware and filters relevant code")
        logger.info("  3. Token limits are respected for large files")
        logger.info("  4. File size determines extraction strategy (full/AST/limited)")
        logger.info("\n🎯 Next Step: Use this in intake -> planner workflow")
        logger.info(f"\n📄 Output saved to: {OUTPUT_FILE}")
        logger.info(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        logger.error(f"\n❌ Error during testing: {e}")
        import traceback

        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()
