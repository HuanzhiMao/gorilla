"""
Sanity check: ensure no duplicate method names across servers within a test case.

For each multi-turn test entry, this script loads the classes listed in
`involved_classes`, inspects their public methods, and flags any method name
that appears in more than one class. Duplicate names cause silent overwrites
in the `class_method_name_mapping` dict used during evaluation.

To run this script, use the following command:
```
cd multimodal-function-call-leaderboard
python -m mfcl_eval.scripts.check_duplicate_method_names
```
"""

import importlib
import inspect
import sys
from collections import defaultdict

from mfcl_eval.constants.category_mapping import TEXT_MULTI_TURN_CATEGORY
from mfcl_eval.constants.eval_config import TEXT_DATASET_PATH
from mfcl_eval.constants.executable_backend_config import CLASS_FILE_PATH_MAPPING
from mfcl_eval.utils import get_base_category, load_file

# Cache: class_name -> list of public method names
_class_methods_cache: dict[str, list[str]] = {}


def get_public_methods(class_name: str) -> list[str]:
    """Return the public method names for a server class (cached)."""
    if class_name in _class_methods_cache:
        return _class_methods_cache[class_name]

    module_path = CLASS_FILE_PATH_MAPPING.get(class_name)
    if module_path is None:
        print(f"  WARNING: class '{class_name}' not found in CLASS_FILE_PATH_MAPPING, skipping")
        _class_methods_cache[class_name] = []
        return []

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    instance = cls()

    IGNORED_METHODS = {"_apply_patch", "_register_patch"}
    methods = [
        name
        for name, _ in inspect.getmembers(instance, predicate=inspect.ismethod)
        if not name.startswith("_") and name not in IGNORED_METHODS
    ]
    _class_methods_cache[class_name] = methods
    return methods


def check_duplicates() -> int:
    """Check all multi-turn data files for duplicate method names. Returns the number of violations."""
    total_violations = 0

    for category in [1]:
        # base_category = get_base_category(category)
        # filepath = TEXT_DATASET_PATH / f"{base_category}.json"
        # if not filepath.exists():
        #     print(f"Skipping {category} (file not found)")
        #     continue

        filepath = "./mfcl_eval/data/text/failing_tools.json"
        entries = load_file(filepath)
        file_violations = 0

        for entry in entries:
            entry_id = entry["id"]
            involved_classes = entry.get("involved_classes", [])

            if len(involved_classes) < 2:
                continue

            # Map each method name to the list of classes that define it
            method_to_classes: dict[str, list[str]] = defaultdict(list)
            for class_name in involved_classes:
                for method_name in get_public_methods(class_name):
                    method_to_classes[method_name].append(class_name)

            duplicates = {
                method: classes
                for method, classes in method_to_classes.items()
                if len(classes) > 1
            }

            if duplicates:
                file_violations += 1
                total_violations += 1
                print(f"\n  DUPLICATE in {entry_id}:")
                for method, classes in sorted(duplicates.items()):
                    print(f"    method '{method}' defined in: {', '.join(classes)}")

        status = "PASS" if file_violations == 0 else f"FAIL ({file_violations} entries with duplicates)"
        print(f"\n[{status}] {category} ({len(entries)} entries checked)")

    return total_violations


def main():
    print("Checking for duplicate method names across servers in multi-turn test cases...\n")
    violations = check_duplicates()

    if violations:
        print(f"\nFAILED: {violations} test entry(s) have duplicate method names across servers.")
        sys.exit(1)
    else:
        print("\nPASSED: No duplicate method names found across servers.")
        sys.exit(0)


if __name__ == "__main__":
    main()
