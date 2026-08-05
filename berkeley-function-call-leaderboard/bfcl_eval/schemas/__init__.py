"""Typed data model for BFCL datasets, ground truth, and generated artifacts.

The package depends only on ``bfcl_eval.constants`` and reads no dataset files of
its own -- it turns raw JSON objects into typed ones and back. Reading and writing
lives in ``bfcl_eval.dataset_loader``. Keeping the split means the round-trip tests
need no filesystem and ``scripts/`` can import the model without dragging in the
loading stack.

Import from here rather than from the submodules::

    from bfcl_eval.schemas import Conversation, FunctionDoc, Message, TestCategory
"""

from bfcl_eval.schemas.category import (
    CATEGORY_SPECS,
    CategoryFamily,
    CategorySpec,
    EvalStrategy,
    TestCategory,
    all_categories,
)
from bfcl_eval.schemas.entries import (
    AgenticTestEntry,
    AstTestEntry,
    FailingToolsTestEntry,
    MemoryPrereqTestEntry,
    MemoryTestEntry,
    MultiTurnTestEntry,
    TestEntry,
    VisionTestEntry,
    entry_class_for,
    parse_test_entry,
)
from bfcl_eval.schemas.environment import (
    FailureInjection,
    HoldoutCondition,
    MissedClassRule,
    ToolEnvironment,
)
from bfcl_eval.schemas.function_doc import UNSET, FunctionDoc, ParameterSchema
from bfcl_eval.schemas.ground_truth import (
    GROUND_TRUTH_CLASSES,
    OMITTED,
    AstGroundTruth,
    CallConstraintGroundTruth,
    CoordinateGroundTruth,
    ExpectedFunctionCall,
    GroundTruth,
    GroundTruthKind,
    MultiTurnGroundTruth,
    NoGroundTruth,
    ResponseRubric,
    TextAnswerGroundTruth,
    parse_ground_truth,
)
from bfcl_eval.schemas.message import (
    AudioContent,
    AudioSource,
    Conversation,
    ImageContent,
    Message,
    Role,
    Turn,
)
from bfcl_eval.schemas.results import ModelResultEntry, ScoreHeader, ScoreRecord
from bfcl_eval.schemas.serde import (
    KNOWN_ANNOTATION_KEYS,
    KNOWN_UNMODELED_KEYS,
    dump_extras,
    split_known,
    warn_once,
)

__all__ = [
    # category
    "CATEGORY_SPECS",
    "CategoryFamily",
    "CategorySpec",
    "EvalStrategy",
    "TestCategory",
    "all_categories",
    # entries
    "AgenticTestEntry",
    "AstTestEntry",
    "FailingToolsTestEntry",
    "MemoryPrereqTestEntry",
    "MemoryTestEntry",
    "MultiTurnTestEntry",
    "TestEntry",
    "VisionTestEntry",
    "entry_class_for",
    "parse_test_entry",
    # message
    "AudioContent",
    "AudioSource",
    "Conversation",
    "ImageContent",
    "Message",
    "Role",
    "Turn",
    # function_doc
    "FunctionDoc",
    "ParameterSchema",
    "UNSET",
    # environment
    "FailureInjection",
    "HoldoutCondition",
    "MissedClassRule",
    "ToolEnvironment",
    # ground_truth
    "AstGroundTruth",
    "CallConstraintGroundTruth",
    "CoordinateGroundTruth",
    "ExpectedFunctionCall",
    "GroundTruth",
    "GroundTruthKind",
    "GROUND_TRUTH_CLASSES",
    "MultiTurnGroundTruth",
    "NoGroundTruth",
    "OMITTED",
    "ResponseRubric",
    "TextAnswerGroundTruth",
    "parse_ground_truth",
    # results
    "ModelResultEntry",
    "ScoreHeader",
    "ScoreRecord",
    # serde
    "KNOWN_ANNOTATION_KEYS",
    "KNOWN_UNMODELED_KEYS",
    "dump_extras",
    "split_known",
    "warn_once",
]
