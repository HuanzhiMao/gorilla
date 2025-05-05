import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple

from bfcl.eval_checker.multi_turn_eval.func_source_code.memory_api_metaclass import (
    MemoryAPI,
)
from bfcl.utils import extract_test_category_from_id, is_first_memory_prereq_entry


MAX_MEMORY_ENTRY_LENGTH = 10000  # 10k characters


class MemoryAPI_rec_sum(MemoryAPI):
    """
    A class that provides APIs to manage memory data in a key-value format.
    """

    def __init__(self):
        self.memory = ""
        self._api_description = """This tool belongs to the memory suite, which provides APIs to interact with a key-value based memory system."""
        self.snapshot_folder = None

    def _load_scenario(self, initial_config: dict, long_context: bool = False):
        # We don't care about the long_context parameter here
        # It's there to match the signature of functions in the multi-turn evaluation code
        model_result_dir: Path = initial_config["model_result_dir"]
        self.test_id: str = initial_config["test_id"]
        self.scenario: str = initial_config["scenario"]
        test_category: str = extract_test_category_from_id(self.test_id, remove_prereq=True)

        # TODO: use helper function to assemble the path
        self.snapshot_folder = model_result_dir / "memory_snapshot" / test_category
        self.snapshot_folder.mkdir(parents=True, exist_ok=True)
        self.latest_snapshot_file = self.snapshot_folder / f"{self.scenario}_final.json"

        if not is_first_memory_prereq_entry(self.test_id):
            assert (
                self.latest_snapshot_file.exists()
            ), f"Not first memory entry, but no snapshot file found in this path: {self.latest_snapshot_file}"

            with open(self.latest_snapshot_file, "r") as f:
                memory_data = json.load(f)
                self.memory = deepcopy(memory_data["memory"])
                self.archival_memory = deepcopy(memory_data["archival_memory"])

    def _flush_memory_to_local_file(self):
        """
        Flush (save) current memory to a local JSON file.
        """

        # Write the snapshot file for the current test entry
        with open(self.snapshot_folder / f"{self.test_id}.json", "w") as f:
            json.dump(
                {
                    "memory": self.memory,
                },
                f,
                indent=4,
            )

        # Update the latest snapshot file content
        with open(self.latest_snapshot_file, "w") as f:
            json.dump(
                {
                    "memory": self.memory,
                },
                f,
                indent=4,
            )

    def _dump_core_memory_to_context(self) -> str:
        if not self.memory:
            return "There is no content in the memory at this point."

        return str(self.memory)


    def memory_add(self, key: str, value: str) -> Dict[str, str]:
        """
        Add a key-value pair to the short-term memory. Make sure to use meaningful keys for easy retrieval later.

        Args:
            key (str): The key under which the value is stored. The key should be unique and case-sensitive. Keys must be snake_case and cannot contain spaces.
            value (str): The value to store in the short-term memory.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if len(self.memory) >= MAX_CORE_MEMORY_SIZE:
            return {"error": "Core memory is full. Please clear some entries."}
        if len(value) > MAX_CORE_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_CORE_MEMORY_ENTRY_LENGTH} characters."
            }

        if not self._is_valid_key_format(key):
            return {"error": "Key must be in snake_case format and cannot contain spaces."}
        if key in self.memory:
            return {"error": "Key name must be unique."}

        self.memory[key] = value
        return {"status": "Key-value pair added."}

    def core_memory_remove(self, key: str) -> Dict[str, str]:
        """
        Remove a key-value pair from the short-term memory.

        Args:
            key (str): The key to remove from the short-term memory. Case-sensitive.

        Returns:
            status (str): Status of the operation.
        """
        if key in self.memory:
            del self.memory[key]
            return {"status": "Key removed."}
        else:
            return {"error": "Key not found."}

    def core_memory_replace(self, key: str, value: str) -> Dict[str, str]:
        """
        Replace a key-value pair in the short-term memory with a new value.

        Args:
            key (str): The key to replace in the short-term memory. Case-sensitive.
            value (str): The new value associated with the key.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if key not in self.memory:
            return {"error": "Key not found."}
        if len(value) > MAX_CORE_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_CORE_MEMORY_ENTRY_LENGTH} characters."
            }

        self.memory[key] = value
        return {"status": "Key replaced."}

    def core_memory_clear(self) -> Dict[str, str]:
        """
        Clear all key-value pairs from the short-term memory, including those from previous interactions. This operation is irreversible.

        Returns:
            status (str): Status of the operation.
        """
        self.memory = {}
        return {"status": "Short term memory cleared."}

    def core_memory_retrieve(self, key: str) -> Dict[str, str]:
        """
        Retrieve the value associated with a key from the short-term memory. This function does not support partial key matching or similarity search.

        Args:
            key (str): The key to retrieve. Case-sensitive. The key must match exactly with the key stored in the memory.

        Returns:
            value (str): The value associated with the key.

        """
        if key not in self.memory:
            return {"error": "Key not found."}
        return {"value": self.memory[key]}

    def core_memory_retrieve_all(self) -> Dict[str, str]:
        """
        Retrieve all key-value pairs from the short-term memory.

        Returns:
            key (str): Each key in the short-term memory.
            value (str): The value associated with each key.
        """
        return self.memory

