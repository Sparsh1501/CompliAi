#!/usr/bin/env python3
"""Test MongoDB and Qdrant connectivity"""
import sys
sys.path.insert(0, '/Users/shivamchandrs/Desktop/legal-tech/compliAi/backend')

try:
    from pymongo import MongoClient
    print("Testing MongoDB connection...")
    client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
    databases = client.list_database_names()
    print(f"✓ MongoDB accessible")
    print(f"  Databases: {databases}")
except Exception as e:
    print(f"✗ MongoDB NOT accessible: {e}")
    sys.exit(1)

try:
    from qdrant_client import QdrantClient
    print("\nTesting Qdrant connection...")
    qdrant = QdrantClient(host="localhost", port=6333, timeout=2)
    collections = qdrant.get_collections()
    print(f"✓ Qdrant accessible")
    print(f"  Collections: {[c.name for c in collections.collections]}")
except Exception as e:
    print(f"✗ Qdrant NOT accessible: {e}")
    sys.exit(1)

print("\n✓ Both databases are accessible")
