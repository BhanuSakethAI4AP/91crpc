"""
MongoDB connection test and collection explorer.
Fetches all collections, sample documents, and indexes from the configured database.
"""
from pymongo import MongoClient
from pprint import pprint
from config import (
    build_mongo_uri,
    MONGO_DB_NAME,
    MONGO_SERVER_SELECTION_TIMEOUT_MS,
    MONGO_CONN_TIMEOUT_MS,
    MONGO_MIN_POOL_SIZE,
    MONGO_MAX_POOL_SIZE,
    MONGO_TLS,
)


def create_mongo_client() -> MongoClient:
    """
    Create and return a configured MongoDB client.
    
    Returns:
        MongoClient: Configured MongoDB client instance
    """
    mongo_uri = build_mongo_uri()
    
    client = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=MONGO_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=MONGO_CONN_TIMEOUT_MS,
        minPoolSize=MONGO_MIN_POOL_SIZE,
        maxPoolSize=MONGO_MAX_POOL_SIZE,
        tls=MONGO_TLS,
    )
    
    return client


def display_collection_info(collection_name: str, db) -> None:
    """
    Display detailed information about a MongoDB collection.
    
    Args:
        collection_name: Name of the collection to inspect
        db: MongoDB database instance
    """
    collection = db[collection_name]
    print("---------------------------------------------------")
    print(f"📂 Collection: {collection_name}")
    
    # Count documents
    doc_count = collection.count_documents({})
    print(f"📊 Total Documents: {doc_count}")
    
    # Get one sample document
    sample_doc = collection.find_one()
    if sample_doc:
        print("\n🧾 Sample Document:")
        pprint(sample_doc)
    else:
        print("\n⚠️  No documents found in this collection.")
    
    # Get index information
    indexes = collection.index_information()
    print("\n📇 Indexes:")
    pprint(indexes)
    
    print("---------------------------------------------------\n")


def main() -> None:
    """
    Main function to connect to MongoDB and display all collections and their info.
    """
    try:
        # Validate database name
        if not MONGO_DB_NAME:
            raise RuntimeError("❌ MONGO_DB_NAME is not configured")
        
        # Create client and ping
        client = create_mongo_client()
        client.admin.command("ping")
        
        # Get database
        db = client[MONGO_DB_NAME]
        
        # List all collections
        collections = sorted(db.list_collection_names())
        
        print(f"\n✅ Connected to MongoDB database: {MONGO_DB_NAME}")
        print(f"📚 Found {len(collections)} collection(s)\n")
        
        if not collections:
            print("⚠️  No collections found in this database.")
            return
        
        # Display info for each collection
        for coll_name in collections:
            display_collection_info(coll_name, db)
        
        print("✅ Done fetching all collections and indexes.")
        
    except RuntimeError as e:
        print(f"❌ Configuration Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        # Close the connection
        if 'client' in locals():
            client.close()
            print("🔌 MongoDB connection closed.")


if __name__ == "__main__":
    main()
