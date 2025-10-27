"""
Purpose: MongoDB client bootstrap (singleton connection, FastAPI-friendly).
Provides thread-safe singleton access to MongoDB client and database.
"""

from __future__ import annotations
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database

# Import app config
from config import (
    build_mongo_uri,
    MONGO_DB_NAME,
    MONGO_MIN_POOL_SIZE,
    MONGO_MAX_POOL_SIZE,
    MONGO_CONN_TIMEOUT_MS,
    MONGO_SERVER_SELECTION_TIMEOUT_MS,
    MONGO_TLS,
    APP_NAME,
)


# Singleton client instance
_MONGO_CLIENT: Optional[MongoClient] = None


def get_client() -> MongoClient:
    """
    Returns a singleton MongoClient instance with pool/timeouts/TLS from config.
    
    The client is lazily initialized on first call and reused for subsequent calls.
    Connection pooling is handled automatically by PyMongo.
    
    Returns:
        MongoClient: Configured MongoDB client instance
        
    Raises:
        RuntimeError: If MongoDB URI cannot be constructed or connection fails
    """
    global _MONGO_CLIENT

    if _MONGO_CLIENT is None:
        try:
            mongo_uri = build_mongo_uri()
            _MONGO_CLIENT = MongoClient(
                mongo_uri,
                appName=APP_NAME,
                uuidRepresentation="standard",
                minPoolSize=MONGO_MIN_POOL_SIZE,
                maxPoolSize=MONGO_MAX_POOL_SIZE,
                connectTimeoutMS=MONGO_CONN_TIMEOUT_MS,
                serverSelectionTimeoutMS=MONGO_SERVER_SELECTION_TIMEOUT_MS,
                tls=MONGO_TLS,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize MongoDB client: {e}") from e

    return _MONGO_CLIENT


def get_database() -> Database:
    """
    Returns the MongoDB database object using MONGO_DB_NAME from config.
    
    Returns:
        Database: MongoDB database instance
        
    Raises:
        RuntimeError: If MONGO_DB_NAME is not set in configuration
    """
    if not MONGO_DB_NAME:
        raise RuntimeError("MONGO_DB_NAME is not configured")

    client = get_client()
    return client[MONGO_DB_NAME]


def check_db_connection() -> bool:
    """
    Lightweight health check to verify database connectivity.
    
    Executes a ping command against the MongoDB admin database.
    
    Returns:
        bool: True if connection is successful
        
    Raises:
        RuntimeError: If connection fails or ping command errors
    """
    try:
        client = get_client()
        client.admin.command("ping")
        return True
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}") from e


def close_connection() -> None:
    """
    Gracefully close the MongoDB client connection.
    
    Should be called during application shutdown (e.g., FastAPI shutdown event).
    Resets the singleton client to None, allowing a fresh connection on next get_client().
    """
    global _MONGO_CLIENT
    
    if _MONGO_CLIENT is not None:
        _MONGO_CLIENT.close()
        _MONGO_CLIENT = None


def get_collection(collection_name: str):
    """
    Get a specific collection from the database.
    
    Args:
        collection_name: Name of the collection (should be snake_case plural)
        
    Returns:
        Collection: MongoDB collection instance
        
    Example:
        >>> contacts = get_collection("contacts")
        >>> users = get_collection("users")
    """
    db = get_database()
    return db[collection_name]
