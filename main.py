import os
import json
import shutil
import networkx as nx
from networkx.readwrite import json_graph
from git import Repo
from src.ingestor import get_code_data, enrich_block

# CONFIGURATION
MEMORY_DIR = "memory"
MEMORY_FILE = os.path.join(MEMORY_DIR, "lumis_memory.json")
GRAPH_FILE = os.path.join(MEMORY_DIR, "lumis_graph.json")
TEMP_PATH = "temp_project"

def run_lumis(repo_url):
    print(f"🚀 Initializing Lumis Engine for: {repo_url}")
    
    # 1. Clean & Clone
    if os.path.exists(TEMP_PATH):
        print("Cleaning up old workspace...")
        try:
            shutil.rmtree(TEMP_PATH)
        except Exception as e:
            print(f"Cleanup Warning: {e}")
    
    print("Cloning repository (shallow)...")
    Repo.clone_from(repo_url, TEMP_PATH, depth=1)

    G = nx.DiGraph()
    full_memory = []
    
    # 2. Ingest & Process
    print("Extracting code units and generating summaries...")
    for root, _, files in os.walk(TEMP_PATH):
        if ".git" in root: continue
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, TEMP_PATH)
            
            # Identify functions/classes via Tree-sitter
            code_units = get_code_data(file_path)
            
            for unit in code_units:
                # Get LLM intelligence (Summary + Embeddings)
                intel = enrich_block(unit['code'])
                
                if intel:
                    node_id = f"{rel_path}::{unit['name']}"
                    
                    # Add to JSON Memory
                    full_memory.append({
                        "id": node_id,
                        "file_path": rel_path,
                        "summary": intel["summary"],
                        "embedding": intel["embedding"]
                    })
                    
                    # Add to Relationship Graph
                    G.add_node(node_id, summary=intel["summary"])
                    for call in unit['calls']:
                        G.add_edge(node_id, call)
    # Final step: Cleanup
    print("Cleaning up temporary files...")
    if os.path.exists(TEMP_PATH):
        try:
            shutil.rmtree(TEMP_PATH)
            print("Temp workspace cleared.")
        except Exception as e:
            print(f"Cleanup failed: {e}")

    # 3. Persistence
    if not os.path.exists(MEMORY_DIR):
        os.makedirs(MEMORY_DIR)

    with open(MEMORY_FILE, "w") as f:
        json.dump(full_memory, f, indent=4)
            
    with open(GRAPH_FILE, "w") as f:
        json.dump(json_graph.node_link_data(G), f, indent=4)
    
    print("-" * 30)
    print(f"✅ Digital Twin Build Complete.")
    print(f"Stored {len(full_memory)} units in {MEMORY_FILE}")

if __name__ == "__main__":
    TARGET_REPO = "https://github.com/racemdammak/cstam-final"
    run_lumis(TARGET_REPO)
    os.remove("temp_project")