#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'Ingestion Documents - RAG ChromaDB
Indexe tous les documents du dossier documents/ dans ChromaDB
"""

import os
import chromadb
from chromadb.config import Settings
from pathlib import Path

# ========================================
# CONFIGURATION
# ========================================

# URL de ChromaDB (container Docker)
CHROMA_HOST = "localhost"
CHROMA_PORT = 8000

# Nom de la collection ChromaDB
COLLECTION_NAME = "homelab_docs"

# Dossier contenant les documents à indexer
DOCUMENTS_DIR = Path(__file__).parent.parent / "documents"

# Taille des morceaux de texte (chunks)
CHUNK_SIZE = 500  # caractères par chunk
CHUNK_OVERLAP = 50  # chevauchement entre chunks

# ========================================
# FONCTIONS
# ========================================

def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    Découpe un texte en morceaux (chunks) avec chevauchement.
    
    Pourquoi découper ?
    - Les embeddings ont une taille max (~500 tokens)
    - Des petits morceaux = recherche plus précise
    - Le chevauchement évite de couper des phrases importantes
    
    Args:
        text (str): Texte à découper
        chunk_size (int): Taille max d'un chunk en caractères
        overlap (int): Nombre de caractères en commun entre chunks
        
    Returns:
        list: Liste de morceaux de texte
    """
    chunks = []
    start = 0
    text_length = len(text)
    
    while start < text_length:
        # Fin du chunk
        end = start + chunk_size
        
        # Récupérer le morceau
        chunk = text[start:end]
        
        # Ajouter à la liste si non vide
        if chunk.strip():
            chunks.append(chunk.strip())
        
        # Avancer avec chevauchement
        start = end - overlap
    
    return chunks


def ingest_documents():
    """
    Fonction principale : Ingestion de tous les documents dans ChromaDB
    """
    
    print("=" * 60)
    print("🚀 INGESTION DOCUMENTS - RAG ChromaDB")
    print("=" * 60)
    
    # ========================================
    # 1. CONNEXION À CHROMADB
    # ========================================
    print("\n📡 Connexion à ChromaDB...")
    
    try:
        # Client HTTP vers container ChromaDB
        client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # Test de connexion
        client.heartbeat()
        print("✅ Connexion ChromaDB OK")
        
    except Exception as e:
        print(f"❌ Erreur connexion ChromaDB : {e}")
        print("💡 Vérifier que le container chromadb tourne : docker ps")
        return
    
    # ========================================
    # 2. CRÉATION/RÉCUPÉRATION COLLECTION
    # ========================================
    print(f"\n📚 Gestion collection '{COLLECTION_NAME}'...")
    
    try:
        # Récupérer collection existante OU créer si n'existe pas
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Documents homelab pour RAG"}
        )
        print(f"✅ Collection '{COLLECTION_NAME}' prête")
        
        # Afficher nombre de documents actuels
        current_count = collection.count()
        print(f"📊 Documents actuellement indexés : {current_count}")
        
        # Option : Réinitialiser la collection
        if current_count > 0:
            reset = input("\n⚠️  Documents déjà présents. Réinitialiser ? (o/N) : ")
            if reset.lower() == 'o':
                client.delete_collection(name=COLLECTION_NAME)
                collection = client.create_collection(
                    name=COLLECTION_NAME,
                    metadata={"description": "Documents homelab pour RAG"}
                )
                print("🔄 Collection réinitialisée")
        
    except Exception as e:
        print(f"❌ Erreur collection : {e}")
        return
    
    # ========================================
    # 3. LECTURE ET INDEXATION DOCUMENTS
    # ========================================
    print(f"\n📂 Lecture documents depuis : {DOCUMENTS_DIR}")
    
    # Vérifier que le dossier existe
    if not DOCUMENTS_DIR.exists():
        print(f"❌ Dossier {DOCUMENTS_DIR} n'existe pas")
        return
    
    # Compteurs
    total_docs = 0
    total_chunks = 0
    errors = 0
    
    # Parcourir tous les fichiers .txt, .md
    for doc_file in DOCUMENTS_DIR.rglob("*.txt"):
        try:
            print(f"\n📄 Traitement : {doc_file.name}")
            
            # Lire le contenu
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Découper en chunks
            chunks = chunk_text(content)
            num_chunks = len(chunks)
            
            print(f"   ✂️  Découpé en {num_chunks} morceaux")
            
            # Préparer les données pour ChromaDB
            documents_list = chunks
            
            ids_list = [
                f"{doc_file.stem}_chunk_{i}"
                for i in range(num_chunks)
            ]
            
            metadatas_list = [
                {
                    "source": str(doc_file.name),
                    "chunk_index": i,
                    "total_chunks": num_chunks
                }
                for i in range(num_chunks)
            ]
            
            # Ajouter à ChromaDB (embeddings créés automatiquement)
            collection.add(
                documents=documents_list,
                ids=ids_list,
                metadatas=metadatas_list
            )
            
            print(f"   ✅ Indexé : {num_chunks} morceaux")
            
            total_docs += 1
            total_chunks += num_chunks
            
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            errors += 1
    
    # ========================================
    # 4. RÉSUMÉ
    # ========================================
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DE L'INGESTION")
    print("=" * 60)
    print(f"✅ Documents traités : {total_docs}")
    print(f"✅ Morceaux indexés : {total_chunks}")
    print(f"❌ Erreurs : {errors}")
    print(f"📚 Collection : {COLLECTION_NAME}")
    print(f"🔢 Total items dans ChromaDB : {collection.count()}")
    print("=" * 60)


def test_search():
    """
    Fonction de test : Recherche sémantique dans ChromaDB
    """
    print("\n" + "=" * 60)
    print("🔍 TEST DE RECHERCHE SÉMANTIQUE")
    print("=" * 60)
    
    # Connexion
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    
    try:
        collection = client.get_collection(name=COLLECTION_NAME)
    except Exception as e:
        print(f"❌ Collection introuvable : {e}")
        return
    
    # Question test
    query = "Quels sont les ports utilisés dans le homelab ?"
    print(f"\n❓ Question : {query}")
    
    # Recherche (ChromaDB va créer l'embedding de la question et comparer)
    results = collection.query(
        query_texts=[query],
        n_results=3  # Top 3 résultats les plus pertinents
    )
    
    # Afficher les résultats
    print("\n📄 Top 3 résultats pertinents :\n")
    
    for i, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    ), 1):
        print(f"--- Résultat #{i} (score: {distance:.4f}) ---")
        print(f"Source : {metadata['source']}")
        print(f"Contenu :\n{doc}\n")
    
    print("=" * 60)


# ========================================
# POINT D'ENTRÉE
# ========================================

if __name__ == "__main__":
    # Ingestion des documents
    ingest_documents()
    
    # Test de recherche
    test_choice = input("\n🔍 Lancer un test de recherche ? (o/N) : ")
    if test_choice.lower() == 'o':
        test_search()
    
    print("\n✅ Script terminé !")
