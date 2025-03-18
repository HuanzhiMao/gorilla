import json
import shutil
from copy import deepcopy
from pathlib import Path

from bfcl.utils import (
    extract_test_category_from_id,
    is_first_memory_prereq_entry,
    is_memory_prereq,
)
from rank_bm25 import BM25Plus

MAX_SHORT_TERM_MEMORY_SIZE = 7
MAX_SHORT_TERM_MEMORY_ENTRY_LENGTH = 300
MAX_LONG_TERM_MEMORY_SIZE = 100  # FIXME: Change this to 50
MAX_LONG_TERM_MEMORY_ENTRY_LENGTH = 2000


class MemoryAPI:
    """
    A class that provides APIs to manage short-term and long-term memory data.
    """

    def __init__(self):
        self.short_term_memory = {}
        self.long_term_memory = {}
        self._api_description = """This tool belongs to the memory suite, which provides APIs to manage both short-term and long-term memory data. Short-term memory is limited in size and can be accessed quickly, while long-term memory is larger but takes longer to access. Both type of memory is persistent across multiple conversations with the user, and can be accessed in a later interactions. You should actively manage the memory data to ensure that it is up-to-date and easy to retrieve later."""

    def _load_scenario(self, initial_config: dict, long_context: bool = False):
        # We don't care about the long_context parameter here
        # It's there to match the signature of functions in the multi-turn evaluation code
        result_dir: Path = initial_config["result_dir"]
        model_name_dir: str = initial_config["model_name_dir"]
        test_entry_id: str = initial_config["test_entry_id"]
        test_category: str = extract_test_category_from_id(test_entry_id)
        target_dir = result_dir / model_name_dir / "memory_snapshot"
        if is_memory_prereq(test_category):
            target_file = target_dir / f"{test_category}_final.json"
        else:
            target_file = target_dir / f"{test_category}_prereq_final.json"

        # TODO: Use a more elegant way to handle this
        if is_first_memory_prereq_entry(test_entry_id):
            if target_dir.exists():
                # Removes the folder and all its contents
                for item in target_dir.iterdir():
                    if item.is_dir():
                        # Remove subdirectory and its contents
                        shutil.rmtree(item)
                    else:
                        # Remove file
                        item.unlink()
            else:
                target_dir.mkdir(parents=True, exist_ok=True)

            # TODO: Move this to the generation pipeline section
            if (
                result_dir / model_name_dir / f"BFCL_v3_{test_category}_result.json"
            ).exists():
                (
                    result_dir / model_name_dir / f"BFCL_v3_{test_category}_result.json"
                ).unlink()

        elif target_file.exists():
            with open(target_file, "r") as f:
                memory_data = json.load(f)
                self.short_term_memory = deepcopy(memory_data["short_term_memory"])
                self.long_term_memory = deepcopy(memory_data["long_term_memory"])

        else:
            raise FileNotFoundError(f"Memory snapshot file not found: {target_file}")
            print(f"Memory snapshot file not found: {target_file}")

    def _flush_memory_to_local_file(
        self, result_dir: Path, model_name_dir: str, test_entry_id: str
    ):
        """
        Flush (save) current memory (both short-term and long-term)
        to a local JSON file.
        """
        test_category = extract_test_category_from_id(test_entry_id)

        target_dir = result_dir / model_name_dir / "memory_snapshot"
        target_dir.mkdir(parents=True, exist_ok=True)

        with open(target_dir / f"{test_entry_id}.json", "w") as f:
            json.dump(
                {
                    "short_term_memory": self.short_term_memory,
                    "long_term_memory": self.long_term_memory,
                },
                f,
                indent=4,
            )
        with open(target_dir / f"{test_category}_final.json", "w") as f:
            json.dump(
                {
                    "short_term_memory": self.short_term_memory,
                    "long_term_memory": self.long_term_memory,
                },
                f,
                indent=4,
            )
            
    @staticmethod
    def _similarity_search(query: str, corpus: list[str], k: int = 5):
        """
        Search for the most similar text in the corpus to the query using BM25+ algorithm.

        Args:
            query (str): The query text to search for.
            corpus (list[str]): A list of text strings to search in.
            k (int): The number of results to return.

        Returns:
            ranked_results (list[tuple[float, str]]): A list of tuples containing the BM25+ score and the text string.
        """
        tokenized_corpus = [text.replace("_", " ").lower().split() for text in corpus]
        bm25 = BM25Plus(tokenized_corpus)
        tokenized_query = query.replace("_", " ").lower().split()
        scores = bm25.get_scores(tokenized_query)
        ranked_results = sorted(zip(scores, corpus), key=lambda x: x[0], reverse=True)
        return {"ranked_results": ranked_results[:k]}

    def short_term_memory_add(self, key: str, value: str):
        """
        Add a key-value pair to the short-term memory. Make sure to use meaningful keys for easy retrieval later.

        Args:
            key (str): The key under which the value is stored. The key should be unique and case-sensitive. Keys must be snake_case and cannot contain spaces.
            value (str): The value to store in the short-term memory.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if len(self.short_term_memory) >= MAX_SHORT_TERM_MEMORY_SIZE:
            return {"error": "Short term memory is full. Please clear some entries."}
        if len(value) > MAX_SHORT_TERM_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_SHORT_TERM_MEMORY_ENTRY_LENGTH} characters."
            }
        if key in self.short_term_memory:
            return {"error": "Key name must be unique."}

        self.short_term_memory[key] = value
        return {"status": "Key added."}

    def short_term_memory_remove(self, key: str):
        """
        Remove a key-value pair from the short-term memory.

        Args:
            key (str): The key to remove from the short-term memory. Case-sensitive.

        Returns:
            status (str): Status of the operation.
        """
        if key in self.short_term_memory:
            del self.short_term_memory[key]
            return {"status": "Key removed."}
        else:
            return {"error": "Key not found."}

    def short_term_memory_replace(self, key: str, value: str):
        """
        Replace a key-value pair in the short-term memory with a new value.

        Args:
            key (str): The key to replace in the short-term memory. Case-sensitive.
            value (str): The new value associated with the key.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if key not in self.short_term_memory:
            return {"error": "Key not found."}
        if len(value) > MAX_SHORT_TERM_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_SHORT_TERM_MEMORY_ENTRY_LENGTH} characters."
            }

        self.short_term_memory[key] = value
        return {"status": "Key replaced."}

    def short_term_memory_clear(self):
        """
        Clear all key-value pairs from the short-term memory, including those from previous interactions. This operation is irreversible.

        Returns:
            status (str): Status of the operation.
        """
        self.short_term_memory = {}
        return {"status": "Short term memory cleared."}

    def short_term_memory_retrieve(self, key: str):
        """
        Retrieve the value associated with a key from the short-term memory. This function does not support partial key matching or similarity search.

        Args:
            key (str): The key to retrieve. Case-sensitive. The key must match exactly with the key stored in the memory.

        Returns:
            value (str): The value associated with the key.

        """
        if key not in self.short_term_memory:
            return {"error": "Key not found."}
        return {"value": self.short_term_memory[key]}

    def short_term_memory_list_keys(self):
        """
        List all keys currently in the short-term memory.

        Returns:
            keys (List[str]): A list of all keys in the short-term memory.
        """
        return {"keys": list(self.short_term_memory.keys())}

    def short_term_memory_key_search(self, query: str, k: int = 5):
        """
        Search for key names in the short-term memory that are similar to the query using BM25+ algorithm.

        Args:
            query (str): The query text to search for.
            k (int, optional): The number of results to return.

        Returns:
            ranked_results (list[tuple[float, str]]): A list of tuples containing the BM25+ score and the key.
        """
        keys = deepcopy(list(self.short_term_memory.keys()))
        return self._similarity_search(query, keys, k)

    def short_term_memory_retrieve_all(self):
        """
        Retrieve all key-value pairs from the short-term memory.

        Returns:
            dict: A dictionary of all key-value pairs in the short-term memory.
        """
        return self.short_term_memory

    def long_term_memory_add(self, key: str, value: str):
        """
        Add a key-value pair to the long-term memory. Make sure to use meaningful keys for easy retrieval later.
        Args:
            key (str): The key under which the value is stored. The key should be unique and case-sensitive. Keys must be snake_case and cannot contain spaces.
            value (str): The value to store in the long-term memory.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if len(self.long_term_memory) >= MAX_LONG_TERM_MEMORY_SIZE:
            return {"error": "Long term memory is full. Please clear some entries."}
        if len(value) > MAX_LONG_TERM_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_LONG_TERM_MEMORY_ENTRY_LENGTH} characters."
            }
        if key in self.long_term_memory:
            return {"error": "Key name must be unique."}

        self.long_term_memory[key] = value
        return {"status": "Key added."}

    def long_term_memory_remove(self, key: str):
        """
        Remove a key-value pair from the long-term memory.

        Args:
            key (str): The key to remove from the long-term memory. Case-sensitive.

        Returns:
            status (str): Status of the operation.
        """
        if key in self.long_term_memory:
            del self.long_term_memory[key]
            return {"status": "Key removed."}
        else:
            return {"error": "Key not found."}

    def long_term_memory_replace(self, key: str, value: str):
        """
        Replace a key-value pair in the long-term memory with a new value.

        Args:
            key (str): The key to replace in the long-term memory. Case-sensitive.
            value (str): The new value associated with the key.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if key not in self.long_term_memory:
            return {"error": "Key not found."}
        if len(value) > MAX_LONG_TERM_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_LONG_TERM_MEMORY_ENTRY_LENGTH} characters."
            }

        self.long_term_memory[key] = value
        return {"status": "Key replaced."}

    def long_term_memory_clear(self):
        """
        Clear all key-value pairs from the long-term memory, including those from previous interactions. This operation is irreversible.

        Returns:
            status (str): Status of the operation.
        """
        self.long_term_memory = {}
        return {"status": "Long term memory cleared."}

    def long_term_memory_retrieve(self, key: str):
        """
        Retrieve the value associated with a key from the long-term memory. This function does not support partial key matching or similarity search.

        Args:
            key (str): The key to retrieve. Case-sensitive. The key must match exactly with the key stored in the memory.

        Returns:
            value (str): The value associated with the key.
        """
        if key not in self.long_term_memory:
            return {"error": "Key not found."}
        return {"value": self.long_term_memory[key]}

    def long_term_memory_list_keys(self):
        """
        List all keys currently in the long-term memory.

        Returns:
            keys (List[str]): A list of all keys in the long-term memory.
        """
        return {"keys": list(self.long_term_memory.keys())}

    def long_term_memory_key_search(self, query: str, k: int = 5):
        """
        Search for key names in the long-term memory that are similar to the query using BM25+ algorithm.

        Args:
            query (str): The query text to search for.
            k (int, optional): The number of results to return.

        Returns:
            ranked_results (list[tuple[float, str]]): A list of tuples containing the BM25+ score and the key.
        """
        keys = deepcopy(list(self.long_term_memory.keys()))
        return self._similarity_search(query, keys, k)
