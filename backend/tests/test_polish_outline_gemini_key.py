"""
VoiceSlide AI - Tests for polish_outline gemini_key parameter propagation.
Sprint 2: Bug fixes for model switching (Bugs 2, 3, 5).

These tests verify the function signatures have the correct parameters.
Due to environment dependency constraints, we use AST parsing to verify
function signatures without importing the modules directly.
"""

import ast
import os


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_function_params(filepath, function_name):
    """Parse a Python file's AST and return parameter names for a given function."""
    with open(filepath) as f:
        tree = ast.parse(f.read())

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return [arg.arg for arg in node.args.args]
    return None


def test_polish_outline_has_gemini_key_param():
    """Bug 3: polish_outline() in outline_generator.py should accept gemini_key"""
    filepath = os.path.join(BACKEND_DIR, "services", "outline_generator.py")
    params = get_function_params(filepath, "polish_outline")
    assert params is not None, "polish_outline function not found"
    assert "gemini_key" in params, (
        f"polish_outline must have gemini_key parameter. Found params: {params}"
    )


def test_polish_outline_uses_gemini_key_or_fallback():
    """Bug 3: polish_outline() should use 'gemini_key or GEMINI_API_KEY' pattern"""
    filepath = os.path.join(BACKEND_DIR, "services", "outline_generator.py")
    with open(filepath) as f:
        source = f.read()

    # Find the polish_outline function body and check for the fallback pattern
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "polish_outline":
            # Get the source lines for this function
            func_source = ast.get_source_segment(source, node)
            assert "gemini_key or GEMINI_API_KEY" in func_source, (
                "polish_outline must use 'gemini_key or GEMINI_API_KEY' fallback pattern"
            )
            return

    pytest.fail("polish_outline function not found in outline_generator.py")


def test_step_polish_outline_has_gemini_key_param():
    """Bug 5: step_polish_outline() in pipeline.py should accept gemini_key"""
    filepath = os.path.join(BACKEND_DIR, "services", "pipeline.py")
    params = get_function_params(filepath, "step_polish_outline")
    assert params is not None, "step_polish_outline function not found"
    assert "gemini_key" in params, (
        f"step_polish_outline must have gemini_key parameter. Found params: {params}"
    )


def test_step_polish_outline_passes_gemini_key_to_polish_outline():
    """Bug 5: step_polish_outline should pass gemini_key=gemini_key to polish_outline()"""
    filepath = os.path.join(BACKEND_DIR, "services", "pipeline.py")
    with open(filepath) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "step_polish_outline":
            func_source = ast.get_source_segment(source, node)
            assert "gemini_key=gemini_key" in func_source, (
                "step_polish_outline must pass gemini_key=gemini_key to polish_outline()"
            )
            return

    pytest.fail("step_polish_outline function not found in pipeline.py")


def test_polish_outline_endpoint_has_gemini_headers():
    """Bug 2: /api/polish-outline endpoint should accept x_gemini_key and x_gemini_model headers"""
    filepath = os.path.join(BACKEND_DIR, "main.py")
    with open(filepath) as f:
        source = f.read()

    # Find the polish_outline endpoint function in main.py
    tree = ast.parse(source)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "polish_outline":
            params = [arg.arg for arg in node.args.args]
            assert "x_gemini_key" in params, (
                f"polish_outline endpoint must have x_gemini_key param. Found: {params}"
            )
            assert "x_gemini_model" in params, (
                f"polish_outline endpoint must have x_gemini_model param. Found: {params}"
            )
            found = True
            break

    assert found, "polish_outline endpoint function not found in main.py"


def test_polish_outline_endpoint_passes_gemini_key_to_pipeline():
    """Bug 2: The endpoint should pass gemini_key to step_polish_outline"""
    filepath = os.path.join(BACKEND_DIR, "main.py")
    with open(filepath) as f:
        source = f.read()

    # Find the polish_outline function and check it passes gemini_key
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "polish_outline":
            func_source = ast.get_source_segment(source, node)
            assert "gemini_key=" in func_source, (
                "polish_outline endpoint must pass gemini_key to step_polish_outline"
            )
            return

    pytest.fail("polish_outline endpoint function not found in main.py")


def test_polish_outline_endpoint_stores_gemini_key_in_jobs():
    """Bug 2: The endpoint should store gemini_key in jobs dict"""
    filepath = os.path.join(BACKEND_DIR, "main.py")
    with open(filepath) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "polish_outline":
            func_source = ast.get_source_segment(source, node)
            assert '"gemini_key"' in func_source or "'gemini_key'" in func_source, (
                "polish_outline endpoint must store gemini_key in jobs dict"
            )
            return

    pytest.fail("polish_outline endpoint function not found in main.py")
