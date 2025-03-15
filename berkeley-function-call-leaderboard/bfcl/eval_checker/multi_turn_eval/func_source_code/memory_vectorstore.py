import os
import signal
import json
import shutil
import hashlib
import subprocess
import time
import redis
import random
import faiss
import numpy as np
import pickle
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Tuple, Union, Any
from sentence_transformers import SentenceTransformer

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
EMBEDDING_DIMENSION = 384

class VectorMemoryAPI:
    """
    A class that provides APIs to manage short-term and long-term memory data.
    """

    def __init__(self, port=None):
        self.long_term_memory = {}

        self.port = port if isinstance(port, int) and port > 0 else random.randint(6500, 7000)
        # Check if Redis is already running on this port
        try:
            test_client = redis.Redis(host='localhost', port=self.port, db=0)
            test_client.ping()
            print(f"Redis already running on port {self.port}, reusing connection")
            self.redis_client = test_client
            # ensure not starting new process if not needed
            self.redis_process = None
        except redis.ConnectionError:
            # if server isn't already running, start a new one
            try:
                print(f"Starting Redis server on port {self.port}")
                self.redis_process = subprocess.Popen(["redis-server", "--port", str(self.port)])
                time.sleep(2)
                # Connect to Redis
                self.redis_client = redis.Redis(host='localhost', port=self.port, db=0)
                self.redis_client.ping()
            except Exception as e:
                print(f"Redis server startup failed: {e}")
                # Force terminate if process was started
                if hasattr(self, 'redis_process'):
                    try:
                        os.kill(self.redis_process.pid, signal.SIGKILL)
                    except:
                        pass
                raise
        #init sentence transformer for text embeddings now
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        #need to init faiss index for vector sim. search
        self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)

        #need to create mapping (IDs to Indices in faiss)
        self.id_to_index_map = {}
        self.next_index = 0

        self.short_term_memory_count = 0

        self._api_description = """This tool belongs to the memory suite, which provides APIs to manage both short-term and long-term memory data. Short-term memory is limited in size and can be accessed quickly, while long-term memory is larger but takes longer to access. Both type of memory is persistent across multiple conversations with the user, and can be accessed in a later interactions. You should actively manage the memory data to ensure that it is up-to-date and easy to retrieve later."""
    
    def __del__(self):
        self._cleanup()
    
    def _cleanup(self):
        if hasattr(self, 'redis_process'):
            try:
                self.redis_process.terminate()
                self.redis_process.wait(timeout=3)
                
                if self.redis_process.poll() is None:
                    os.kill(self.redis_process.pid, signal.SIGKILL)
            except:
                pass
    
    def _get_text_embedding(self, text: str) -> np.ndarray:
        embedding = self.embedding_model.encode(text)
        return embedding.astype(np.float32)

    def _generate_text_id(self, text: str) -> str:
        # use md5 to hash for consistent and a fixed lenth uuid
        # used to map text in redis and the faiss index 
        return hashlib.md5(text.encode()).hexdigest()

    def _add_to_vector_store(self, text: str) -> str:
        #We'll add to both faiss and redis in this
        if self.short_term_memory_count >= MAX_SHORT_TERM_MEMORY_SIZE:
            return None
        
        text_id = self._generate_text_id(text)
        embedding = self._get_text_embedding(text)

        #redis
        self.redis_client.set(text_id, text)
        self.redis_client.set(f"vec:{text_id}", pickle.dumps(embedding))

        #faiss
        self.faiss_index.add(np.array([embedding], dtype=np.float32))

        #update id-to-index map
        self.id_to_index_map[text_id] = self.next_index
        self.next_index += 1
        self.short_term_memory_count += 1

        return text_id

    def _remove_from_vector_store(self, text_id: str) -> bool:
        if text_id not in self.id_to_index_map:
            return False

        #redis
        self.redis_client.delete(text_id)
        self.redis_client.delete(f"vec:{text_id}")
        self.short_term_memory_count -= 1

        # for faiss, to actually remove we have to rebuild the index
        # don't need for now, if needed, will create helper func for it

        return True

    def _search_vector_store(self, query: str, k: int = 5) -> List[Tuple[float, str]]:
        query_embedding = self._get_text_embedding(query)

        k = min(k, self.short_term_memory_count)
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
            #after finding our text id we do 3 things
            # 1. get the stored text from redis
            # 2. decode bytes back to a string
            # 3. put the similarity score w/ text and append to results
            if text_id:
                text_bytes = self.redis_client.get(text_id)
                if text_bytes:
                    text = text_bytes.decode('utf-8')
                    results.append((float(distances[0][i]), text))

        return results

    def _export_short_term_memory(self) -> Dict[str, str]:
        # create dictionary for our key-value pairs
        result = {}
        all_keys = self.redis_client.keys("*")
        text_ids = [key.decode() for key in all_keys if not key.decode().startswith("vec:")]

        for text_id in text_ids:
            text_bytes = self.redis_client.get(text_id)
            if text_bytes:
                # use text as both the key and the value pair 
                text = text_bytes.decode('utf-8')
                result[text] = text
        
        return result
    
    def _import_short_term_memory(self, memory_dict: Dict[str, str]):
        #clear redis state
        all_keys = self.redis_client.keys("*")
        for key in all_keys:
            self.redis_client.delete(key)
        
        self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        self.id_to_index_map = {}
        self.next_index = 0
        self.short_term_memory_count = 0

        for value in memory_dict.values():
            self._add_to_vector_store(value)

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
                self._import_short_term_memory(memory_data["short_term_memory"])
                # self.short_term_memory = deepcopy(memory_data["short_term_memory"])
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
                    "short_term_memory": self._export_short_term_memory(),
                    "long_term_memory": self.long_term_memory,
                },
                f,
                indent=4,
            )
        with open(target_dir / f"{test_category}_final.json", "w") as f:
            json.dump(
                {
                    "short_term_memory": self._export_short_term_memory(),
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

    def short_term_memory_add(self, value: str):
        """
        Add a value to the short-term memory vecto store.

        Args:
            value (str): The value to store in the short-term memory.

        Returns:
            status (str): Status of the operation.
        """
        value = str(value)
        if self.short_term_memory_count >= MAX_SHORT_TERM_MEMORY_SIZE:
            return {"error": "Short term memory is full. Please clear some entries."}
        if len(value) > MAX_SHORT_TERM_MEMORY_ENTRY_LENGTH:
            return {
                "error": f"Entry is too long. Please shorten the entry to less than {MAX_SHORT_TERM_MEMORY_ENTRY_LENGTH} characters."
            }
        
        text_id = self._add_to_vector_store(value)

        if text_id is None:
            return {"error": "Failed to add to memory."}
        
        return {"status": "Entry added.", "id": text_id}

    def short_term_memory_remove(self, value: str):
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

    def short_term_memory_clear(self):
        """
        Clear all values from the short-term memory, including those from previous interactions. This operation is irreversible.

        Returns:
            status (str): Status of the operation.
        """
        all_keys = self.redis_client.keys("*")
        for key in all_keys:
            self.redis_client.delete(key)
            
        self.faiss_index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
        self.id_to_index_map = {}
        self.next_index = 0
        self.short_term_memory_count = 0
        
        return {"status": "Short term memory cleared."}

    def short_term_memory_search(self, query: str, k: int = 5):
        """
        Search for similar entries in the short-term memory using vector similarity.

        Args:
            query (str): The query text to search for.
            k (int, optional): The number of results to return.

        Returns:
            ranked_results (list[tuple[float, str]]): A list of tuples containing the similarity score and the text.
        """
        results = self._search_vector_store(query, k)
        return {"ranked_results": results}

    def short_term_memory_retrieve_all(self):
        """
        Retrieve all values from the short-term memory.

        Returns:
            list: A list of all values in the short-term memory.
        """
        all_values = []
        all_keys = self.redis_client.keys("*")
        text_ids = [key.decode() for key in all_keys if not key.decode().startswith("vec:")]
        
        for text_id in text_ids:
            text_bytes = self.redis_client.get(text_id)
            if text_bytes:
                all_values.append(text_bytes.decode('utf-8'))
        
        return {"values": all_values}

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