import ast
from pathlib import Path

BACKEND_PATH_PREFIX = "bfcl_eval.eval_checker.multi_turn_eval.func_source_code"

_FUNC_SOURCE_DIR = (
    Path(__file__).resolve().parents[1]
    / "eval_checker"
    / "multi_turn_eval"
    / "func_source_code"
)

# Utility/infrastructure files that don't contain backend classes
_SKIP_FILES = {
    "__init__.py",
    "memory_api_metaclass.py",
    "server_patch_mixin.py",
    "long_context.py",
}

# Helper classes defined alongside backend classes that should not be registered
_SKIP_CLASSES = {
    "File",
    "Directory",
    "VectorStore",
    "ImageResult",
    "PatchableMixin",
    "MemoryAPI",
}


def _discover_backend_classes():
    """Auto-discover backend classes from .py files in the func_source_code directory.

    Returns:
        class_file_path_mapping: {class_name: dotted_module_path}
        func_doc_file_mapping: {class_name: json_filename}
    """
    class_mapping = {}
    doc_mapping = {}
    for py_file in sorted(_FUNC_SOURCE_DIR.glob("*.py")):
        if py_file.name in _SKIP_FILES:
            continue
        module_path = f"{BACKEND_PATH_PREFIX}.{py_file.stem}"
        with open(py_file) as f:
            tree = ast.parse(f.read())
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef) and node.name not in _SKIP_CLASSES:
                class_mapping[node.name] = module_path
                doc_mapping[node.name] = f"{py_file.stem}.json"
    return class_mapping, doc_mapping


CLASS_FILE_PATH_MAPPING, MULTI_TURN_FUNC_DOC_FILE_MAPPING = _discover_backend_classes()

# These classes are stateless and do not require any initial configuration
STATELESS_CLASSES = [
    "MathAPI",
    "VisionSearchAPI",
    # "StreetViewAPI",
]

# These classes are stateful, but their state is either too verbose to include in the inference log or doesn't provide meaningful insights
# Their state will be displayed and stored in separate files, if needed
OMIT_STATE_INFO_CLASSES = [
    "MemoryAPI_kv",
    "MemoryAPI_vector",
    "MemoryAPI_rec_sum",
    "WebSearchAPI",
    "StreetViewAPI",
]

# These classes might update their available tool list during runtime, after each action.
UPDATED_TOOL_LIST_CLASSES = [
    "StreetViewAPI",
]

# These classes need to be closed after the evaluation is complete
END_SESSION_AFTER_EVAL_CLASSES = [
    "StreetViewAPI",
]
