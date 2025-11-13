"""
CausalIQ Pipeline Actions.

This package contains workflow actions that can be used in CausalIQ workflows.
Each action follows the GitHub Actions pattern with standardised inputs and
outputs.
"""

from .dummy_structure_learner import DummyStructureLearnerAction

__all__ = ["DummyStructureLearnerAction"]
