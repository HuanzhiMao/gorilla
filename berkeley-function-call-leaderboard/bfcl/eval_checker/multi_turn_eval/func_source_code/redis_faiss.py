import subprocess
import time
import redis
import faiss
import numpy as np
import pickle

#used homebrew

# how to embed the text through faiss
# look at what embedding model or if faiss provides one

# Next step, actually contextualizing this code

#spinning up the server with this command
redis_process = subprocess.Popen(["redis-server", "--port", "6500"])

#recommended sleep time to ensure it is running before connecting
time.sleep(2)

#this command is for connecting to the local host
redis_client = redis.Redis(host='localhost', port=6500, db=0)

#proof of concept for integration w/ faiss begans now
d = 768
index = faiss.IndexFlatL2(d)

def add_to_memory(text_id, embedding, text):
    # add text entry to Redis and FAISS
    # text_id is unique id for text (hash of text)
    # embedding is vector embedding (some numpy array)
    # text is the actual string text

    # We should convert the embeddings to bytes for Redis storage
    # This is that conversion
    embedding_bytes = pickle.dumps(embedding)

    # Now we can store the text in Redis
    redis_client.set(text_id, text)

    # In addition, here we are storing the embedding in redis now
    redis_client.set(f"vec:{text_id}", embedding_bytes)

    # Lastly we are doing to be adding it to the index as well
    index.add(np.array([embedding], dtype=np.float32))

    return f"Added {text_id} to memory."


def retrieve_text(text_id):
    #grab the text
    text = redis_client.get(text_id)
    return text.decode("utf-8") if text else None

def search_memory(query_embedding, k=5):
    # Search FAISS for nearest embeddings
    distances, indices = index.search(np.array([query_embedding], dtype=np.float32), k)
    return distances, indices

def test():
    #generating dummy embedding just for now, might use SentenceTransformer
    dummy_embedding = np.random.rand(768).astype(np.float32)
    add_to_memory("entry_1", dummy_embedding, "This is a test memory entry.")

    print("Retrieved:", retrieve_text("entry_1"))

    #similarity search
    query_embedding = np.random.rand(768).astype(np.float32)
    distances, indices = search_memory(query_embedding)
    print("Nearest neighbors:", indices)

    #shut-down server when we are finished
    redis_process.terminate()

test()