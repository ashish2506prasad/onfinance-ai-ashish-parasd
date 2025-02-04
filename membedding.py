from sentence_transformers import SentenceTransformer
from pinecone import Pinecone, ServerlessSpec
import os


bert_model = SentenceTransformer("all-MiniLM-L6-v2")  

PINECONE_API_KEY = "pcsk_4VxnbB_Pbvwn2Zem1iGb55wMQ62aDSmq86BzqLU2a9rWmweU32xBSZMTQMmSEKofoSrNXQ"
REGION = "us-east-1"  
INDEX_NAME = "onfinanceai-assignment"


# Initialize Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY)

# Create index if it doesn’t exist
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(
        name=INDEX_NAME,
        dimension=384,  # Adjust dimension based on model
        metric="cosine",
        spec=ServerlessSpec(cloud="aws", region=REGION)
    )

# Connect to the index
index = pc.Index(INDEX_NAME)

def get_embedding(text):
    """Generate BERT embedding for a given text."""
    return bert_model.encode(text).tolist()  # Convert to list for Pinecone

def store_embedding(text, id):
    """Store text embedding into Pinecone."""
    embedding = get_embedding(text)
    index.upsert(vectors=[(id, embedding, {"text": text})])
    print(f"Stored embedding for ID: {id}")

if __name__ == "__main__":
    store_embedding("This is an example text.", "text_1")