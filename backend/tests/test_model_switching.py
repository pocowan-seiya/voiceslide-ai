"""
VoiceSlide AI - Regression tests for model switching across all endpoints.
Sprint 3: Ensures OpenRouter/Gemini parameters are consistently available
across all relevant endpoints.

Uses AST parsing to verify function signatures without importing modules.
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


def get_function_source(filepath, function_name):
    """Parse a Python file and return the source code of a given function."""
    with open(filepath) as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return ast.get_source_segment(source, node)
    return None


# ============================================================
# /api/polish-outline endpoint: all model parameters
# ============================================================

class TestPolishOutlineEndpoint:
    """Verify polish-outline endpoint accepts all model parameters."""

    def test_has_openrouter_key(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "polish_outline")
        assert params is not None, "polish_outline endpoint not found"
        assert "x_openrouter_key" in params, (
            f"polish_outline endpoint must accept x_openrouter_key. Found: {params}"
        )

    def test_has_openrouter_model(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "polish_outline")
        assert params is not None
        assert "x_openrouter_model" in params, (
            f"polish_outline endpoint must accept x_openrouter_model. Found: {params}"
        )

    def test_has_gemini_key(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "polish_outline")
        assert params is not None
        assert "x_gemini_key" in params, (
            f"polish_outline endpoint must accept x_gemini_key. Found: {params}"
        )

    def test_has_gemini_model(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "polish_outline")
        assert params is not None
        assert "x_gemini_model" in params, (
            f"polish_outline endpoint must accept x_gemini_model. Found: {params}"
        )


# ============================================================
# /api/generate-slides endpoint: OpenRouter parameters
# ============================================================

class TestGenerateSlidesEndpoint:
    """Verify non-batch generate-slides accepts OpenRouter parameters."""

    def test_has_openrouter_key(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "generate_slides_endpoint")
        assert params is not None, "generate_slides_endpoint not found"
        assert "x_openrouter_key" in params, (
            f"generate_slides_endpoint must accept x_openrouter_key. Found: {params}"
        )

    def test_has_openrouter_model(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "generate_slides_endpoint")
        assert params is not None
        assert "x_openrouter_model" in params, (
            f"generate_slides_endpoint must accept x_openrouter_model. Found: {params}"
        )

    def test_has_openrouter_design_model(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "generate_slides_endpoint")
        assert params is not None
        assert "x_openrouter_design_model" in params, (
            f"generate_slides_endpoint must accept x_openrouter_design_model. Found: {params}"
        )

    def test_has_gemini_key(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "generate_slides_endpoint")
        assert params is not None
        assert "x_gemini_key" in params, (
            f"generate_slides_endpoint must accept x_gemini_key. Found: {params}"
        )

    def test_passes_openrouter_to_generate_all_custom_slides(self):
        """generate_slides_endpoint must pass openrouter params to generate_all_custom_slides"""
        filepath = os.path.join(BACKEND_DIR, "main.py")
        source = get_function_source(filepath, "generate_slides_endpoint")
        assert source is not None, "generate_slides_endpoint not found"
        assert "openrouter_key=" in source, (
            "generate_slides_endpoint must pass openrouter_key to generate_all_custom_slides"
        )
        assert "openrouter_model=" in source, (
            "generate_slides_endpoint must pass openrouter_model to generate_all_custom_slides"
        )
        assert "openrouter_design_model=" in source, (
            "generate_slides_endpoint must pass openrouter_design_model to generate_all_custom_slides"
        )


# ============================================================
# /api/generate-slides-batch endpoint: consistency check
# ============================================================

class TestGenerateSlidesBatchEndpoint:
    """Verify batch endpoint has OpenRouter parameters (baseline consistency)."""

    def test_has_openrouter_key(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "generate_slides_batch_endpoint")
        assert params is not None, "generate_slides_batch_endpoint not found"
        assert "x_openrouter_key" in params

    def test_has_openrouter_model(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "generate_slides_batch_endpoint")
        assert params is not None
        assert "x_openrouter_model" in params

    def test_has_openrouter_design_model(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        params = get_function_params(filepath, "generate_slides_batch_endpoint")
        assert params is not None
        assert "x_openrouter_design_model" in params


# ============================================================
# Consistency: non-batch and batch have same OpenRouter params
# ============================================================

class TestEndpointConsistency:
    """Ensure non-batch and batch endpoints have consistent OpenRouter parameters."""

    OPENROUTER_PARAMS = ["x_openrouter_key", "x_openrouter_model", "x_openrouter_design_model"]

    def test_generate_slides_has_all_openrouter_params_from_batch(self):
        filepath = os.path.join(BACKEND_DIR, "main.py")
        non_batch_params = get_function_params(filepath, "generate_slides_endpoint")
        batch_params = get_function_params(filepath, "generate_slides_batch_endpoint")

        assert non_batch_params is not None, "generate_slides_endpoint not found"
        assert batch_params is not None, "generate_slides_batch_endpoint not found"

        for param in self.OPENROUTER_PARAMS:
            assert param in batch_params, (
                f"Batch endpoint missing {param} (baseline broken)"
            )
            assert param in non_batch_params, (
                f"Non-batch endpoint missing {param} that batch endpoint has"
            )
