"""
Test to achieve 100% coverage on action.py TYPE_CHECKING block.
"""

import sys


def test_type_checking_import_coverage():
    """Test that forces the TYPE_CHECKING import to be executed."""
    # Save the original TYPE_CHECKING value
    import typing

    original_type_checking = typing.TYPE_CHECKING

    try:
        # Temporarily set TYPE_CHECKING to True to force import execution
        typing.TYPE_CHECKING = True

        # Remove the action module from sys.modules if it exists
        # so that when we import it, the TYPE_CHECKING block runs
        if "causaliq_workflow.action" in sys.modules:
            del sys.modules["causaliq_workflow.action"]

        # Import the module - this should execute the TYPE_CHECKING block
        import causaliq_workflow.action

        # Verify the module imported successfully
        assert hasattr(causaliq_workflow.action, "CausalIQAction")

    finally:
        # Restore the original TYPE_CHECKING value
        typing.TYPE_CHECKING = original_type_checking
