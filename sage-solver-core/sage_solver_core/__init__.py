"""SAGE Core — Solver-Augmented Generation Engine.

Pure optimization engine: solver wrappers, model building, file I/O,
and result explanation. No deployment opinions, no file system access,
no print statements.
"""

__version__ = "0.1.0"
__author__ = "Pragnakar Pedapenki"
__email__ = "pragnakar@gmail.com"

from sage_solver_core.classifier import ClassificationResult, classify

__all__ = ["__version__", "classify", "ClassificationResult"]
