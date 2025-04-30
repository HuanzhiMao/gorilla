import json
import shutil
import hashlib
import faiss
import numpy as np
from copy import deepcopy
from pathlib import Path
from typing import List, Tuple, Dict
from sentence_transformers import SentenceTransformer

from bfcl.utils import (
    extract_test_category_from_id,
    is_first_memory_prereq_entry,
    is_memory_prereq,
)

from rank_bm25 import BM25Plus

MAX_CORE_MEMORY_SIZE = 7
MAX_CORE_MEMORY_ENTRY_LENGTH = 300
MAX_ARCHIVAL_MEMORY_SIZE = 100  # FIXME: Change this to 50
MAX_ARCHIVAL_MEMORY_ENTRY_LENGTH = 2000
EMBEDDING_DIMENSION = 384

class MemoryAPI_vector:
    """
    A class that provides APIs to manage short-term and long-term memory data.
    """

    def __init__(self):
        self.archival_memory = {}
        #init sentence transformer for text embeddings now
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        #need to init faiss index for vector sim. search
        self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)

        #need to create mapping (IDs to Indices in faiss)
        self.id_to_index_map = {}
        self.next_index = 0

        #setup vector store
        self.text_store = {}
        self.vector_store = {}

        self.core_memory_count = 0

        self._api_description = """This tool belongs to the memory suite, which provides APIs to manage both short-term and long-term memory data. Short-term memory is limited in size and can be accessed quickly, while long-term memory is larger but takes longer to access. Both type of memory is persistent across multiple conversations with the user, and can be accessed in a later interactions. You should actively manage the memory data to ensure that it is up-to-date and easy to retrieve later."""

    def _setup_vector_store(self, port=None, db=0):
        #reset vector store
        self.text_store = {}
        self.vector_store = {}

        # Initialize faiss index if not already done
        if self.faiss_index is None:
            self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        
        # Reset other state variables
        self.id_to_index_map = {}
        self.next_index = 0
        self.core_memory_count = 0
        
        if self.embedding_model is None:
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        return True

    def _get_text_embedding(self, text: str) -> np.ndarray:
        embedding = self.embedding_model.encode(text)
        return embedding.astype(np.float32)

    def _generate_text_id(self, text: str) -> str:
        # use md5 to hash for consistent and a fixed lenth uuid
        # used to map text in redis and the faiss index 
        return hashlib.md5(text.encode()).hexdigest()

    def _add_to_vector_store(self, text: str) -> str:
        #We'll add to both faiss and redis in this
        if self.core_memory_count >= MAX_CORE_MEMORY_SIZE:
            return None
        
        text_id = self._generate_text_id(text)
        embedding = self._get_text_embedding(text)

        #store
        self.text_store[text_id] = text
        self.vector_store[text_id] = embedding

        #faiss
        self.faiss_index.add(np.array([embedding], dtype=np.float32))

        #update id-to-index map
        self.id_to_index_map[text_id] = self.next_index
        self.next_index += 1
        self.core_memory_count += 1
        
        return text_id

    def _remove_from_vector_store(self, text_id: str) -> bool:
        if text_id not in self.id_to_index_map:
            return False

        #remove
        if text_id in self.text_store:
            del self.text_store[text_id]
        if text_id in self.vector_store:
            del self.vector_store[text_id]
        
        self.core_memory_count -= 1

        # for faiss, to actually remove we have to rebuild the index
        # don't need for now, if needed, will create helper func for it

        return True

    def _search_vector_store(self, query: str, k: int = 5) -> List[Tuple[float, str]]:
        query_embedding = self._get_text_embedding(query)

        k = min(k, self.core_memory_count)
        if k <= 0:
            return []

        # performs the actual vector similarity
        # returns distances (similarity scores) and indices (positions in the index)
        distances, indices = self.faiss_index.search(
            np.array([query_embedding], dtype=np.float32), k
        )

        # using our indices, we retrieve text
        results = []
        for i, idx in enumerate(indices[0]):
            text_id = None
            for txt_id, index in self.id_to_index_map.items():
                if index == idx:
                    text_id = txt_id
                    break

            # Get text from our in-memory store
            if text_id and text_id in self.text_store:
                text = self.text_store[text_id]
                results.append((float(distances[0][i]), text))

        return results

    def _export_core_memory(self) -> List[str]:
        result = []
        for text_id in self.text_store:
            result.append(self.text_store[text_id])
        return result

    
    def _import_core_memory(self, memory_list: List[str]):
        # Clear in-memory state
        self.text_store = {}
        self.vector_store = {}
        
        self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        self.id_to_index_map = {}
        self.next_index = 0
        self.core_memory_count = 0

        for text in memory_list:
            self._add_to_vector_store(text)

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
            
        # init vector store
        self._setup_vector_store()

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
                self._import_core_memory(memory_data["core_memory"])
                # self.core_memory = deepcopy(memory_data["core_memory"])
                self.archival_memory = deepcopy(memory_data["archival_memory"])

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
                    "core_memory": self._export_core_memory(),
                    "archival_memory": self.archival_memory,
                },
                f,
                indent=4,
            )
        with open(target_dir / f"{test_category}_final.json", "w") as f:
            json.dump(
                {
                    "core_memory": self._export_core_memory(),
                    "archival_memory": self.archival_memory,
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

    def core_memory_add(self, value: str) -> Dict[str, str]:
        """
        Add a value to the short-term memory vecto store.

        Args:
            value (str): The value to store in the short-term memory.

        Returns:
            status (str): Status of the operation.
        """
        value = str(value)
        if self.core_memory_count >= MAX_CORE_MEMORY_SIZE:
            return {"error": "Short term memory is full. Please clear some entries."}
        if len(value) > MAX_CORE_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_CORE_MEMORY_ENTRY_LENGTH} characters."
            }
        
        text_id = self._add_to_vector_store(value)

        if text_id is None:
            return {"error": "Failed to add to memory."}
        
        return {"status": "Entry added.", "id": text_id}

    def core_memory_remove(self, value: str) -> Dict[str, str]:
        """
        Remove a value from the short-term memory.

        Args:
            value (str): The value to remove from the short-term memory.

        Returns:
            status (str): Status of the operation.
        """
        text_id = self._generate_text_id(value)
        if self._remove_from_vector_store(text_id):
            return {"status": "Entry removed."}
        else:
            return {"error": "Entry not found."}

    def core_memory_clear(self) -> Dict[str, str]:
        """
        Clear all values from the short-term memory, including those from previous interactions. This operation is irreversible.

        Returns:
            status (str): Status of the operation.
        """
        self.text_store = {}
        self.vector_store = {}
            
        self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        self.id_to_index_map = {}
        self.next_index = 0
        self.core_memory_count = 0
        
        return {"status": "Short term memory cleared."}

    def core_memory_search(self, query: str, k: int = 5) -> Dict[str, List[Tuple[float, str]]]:
        """
        Search for similar entries in the short-term memory using vector similarity.

        Args:
            query (str): The query text to search for.
            k (int): [Optional] The number of results to return.

        Returns:
            ranked_results (List[Tuple[float, str]]): A list of tuples containing the similarity score and the text.
        """
        results = self._search_vector_store(query, k)
        return {"ranked_results": results}

    def core_memory_retrieve_all(self) -> Dict[str, List[str]]:
        """
        Retrieve all values from the short-term memory.

        Returns:
            values (List[str]): A list of all values in the short-term memory.
        """
        all_values = list(self.text_store.values())
        return {"values": all_values}

    def archival_memory_add(self, key: str, value: str) -> Dict[str, str]:
        """
        Add a key-value pair to the long-term memory. Make sure to use meaningful keys for easy retrieval later.
        Args:
            key (str): The key under which the value is stored. The key should be unique and case-sensitive. Keys must be snake_case and cannot contain spaces.
            value (str): The value to store in the long-term memory.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if len(self.archival_memory) >= MAX_ARCHIVAL_MEMORY_SIZE:
            return {"error": "Long term memory is full. Please clear some entries."}
        if len(value) > MAX_ARCHIVAL_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_ARCHIVAL_MEMORY_ENTRY_LENGTH} characters."
            }
        if key in self.archival_memory:
            return {"error": "Key name must be unique."}

        self.archival_memory[key] = value
        return {"status": "Key added."}

    def archival_memory_remove(self, key: str) -> Dict[str, str]:
        """
        Remove a key-value pair from the long-term memory.

        Args:
            key (str): The key to remove from the long-term memory. Case-sensitive.

        Returns:
            status (str): Status of the operation.
        """
        if key in self.archival_memory:
            del self.archival_memory[key]
            return {"status": "Key removed."}
        else:
            return {"error": "Key not found."}

    def archival_memory_replace(self, key: str, value: str) -> Dict[str, str]:
        """
        Replace a key-value pair in the long-term memory with a new value.

        Args:
            key (str): The key to replace in the long-term memory. Case-sensitive.
            value (str): The new value associated with the key.

        Returns:
            status (str): Status of the operation.
        """
        key, value = str(key), str(value)
        if key not in self.archival_memory:
            return {"error": "Key not found."}
        if len(value) > MAX_ARCHIVAL_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_ARCHIVAL_MEMORY_ENTRY_LENGTH} characters."
            }

        self.archival_memory[key] = value
        return {"status": "Key replaced."}

    def archival_memory_clear(self) -> Dict[str, str]:
        """
        Clear all key-value pairs from the long-term memory, including those from previous interactions. This operation is irreversible.

        Returns:
            status (str): Status of the operation.
        """
        self.archival_memory = {}
        return {"status": "Long term memory cleared."}

    def archival_memory_retrieve(self, key: str) -> Dict[str, str]:
        """
        Retrieve the value associated with a key from the long-term memory. This function does not support partial key matching or similarity search.

        Args:
            key (str): The key to retrieve. Case-sensitive. The key must match exactly with the key stored in the memory.

        Returns:
            value (str): The value associated with the key.
        """
        if key not in self.archival_memory:
            return {"error": "Key not found."}
        return {"value": self.archival_memory[key]}

    def archival_memory_list_keys(self) -> Dict[str, List[str]]:
        """
        List all keys currently in the long-term memory.

        Returns:
            keys (List[str]): A list of all keys in the long-term memory.
        """
        return {"keys": list(self.archival_memory.keys())}

    def archival_memory_key_search(self, query: str, k: int = 5) -> Dict[str, List[Tuple[float, str]]]:
        """
        Search for key names in the long-term memory that are similar to the query using BM25+ algorithm.

        Args:
            query (str): The query text to search for.
            k (int): [Optional] The number of results to return.

        Returns:
            ranked_results (List[Tuple[float, str]]): A list of tuples containing the BM25+ score and the key.
        """
        keys = deepcopy(list(self.archival_memory.keys()))
        return self._similarity_search(query, keys, k)