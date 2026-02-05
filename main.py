import os
import json
import networkx as nx
from networkx.readwrite import json_graph
from git import Repo
from dotenv import load_dotenv

# Import shared logic
from src.ingestor import get_code_data, enrich_block
from src.services import generate_footprint

load_dotenv()

MEMORY_DIR = "memory"
MEMORY_FILE = os.path.join(MEMORY_DIR, "lumis_memory.json")
GRAPH_FILE = os.path.join(MEMORY_DIR, "lumis_graph.json")
TEMP_PATH = "temp_project"

def run_lumis(repo_url):
    print(f"🚀 Running Non-Destructive Update for: {repo_url}")
    
    # 1. LOAD EXISTING MEMORY (Don't delete!)
    mem_dict = {}
    last_commit = "initial"
    
    if os.path.exists(MEMORY_FILE):
        print("📂 Loading existing memory...")
        with open(MEMORY_FILE, "r") as f:
            old_data = json.load(f)
            # Metadata is at index 0, actual units follow
            if old_data and "last_commit" in old_data[0]:
                last_commit = old_data[0]["last_commit"]
                mem_dict = {item["id"]: item for item in old_data[1:]}
            else:
                mem_dict = {item["id"]: item for item in old_data}

    # 2. Update/Clone Repo
    if not os.path.exists(TEMP_PATH):
        print("Cloning repository...")
        repo = Repo.clone_from(repo_url, TEMP_PATH, depth=1)
    else:
        print("Pulling latest updates...")
        repo = Repo(TEMP_PATH)
        repo.remotes.origin.pull()
    
    new_commit = repo.head.commit.hexsha

    # 3. Process and Merge
    G = nx.DiGraph()
    
    for root, _, files in os.walk(TEMP_PATH):
        if ".git" in root: continue
        for file in files:
            if not file.endswith(('.py', '.js', '.ts', '.rs')): continue
            
            f_path = os.path.join(root, file)
            rel_path = os.path.relpath(f_path, TEMP_PATH)
            
            units = get_code_data(f_path)
            for unit in units:
                node_id = f"{rel_path}::{unit['name']}"
                current_hash = generate_footprint(unit["code"])
                
                # Check if we already have this exact code summarized
                if node_id in mem_dict and mem_dict[node_id].get("footprint") == current_hash:
                    # KEEP OLD DATA - Do nothing
                    pass 
                else:
                    print(f"✨ New or changed: {node_id}")
                    intel = enrich_block(unit["code"], unit["name"])
                    if intel:
                        mem_dict[node_id] = {
                            "id": node_id,
                            "file_path": rel_path,
                            **intel,
                            "calls": unit["calls"]
                        }
                
                # Rebuild Graph from memory
                if node_id in mem_dict:
                    data = mem_dict[node_id]
                    G.add_node(node_id, summary=data["summary"])
                    for call in data.get("calls", []):
                        G.add_edge(node_id, call)

    # 4. Save Final Merged Result
    os.makedirs(MEMORY_DIR, exist_ok=True)
    final_output = [{"last_commit": new_commit}] + list(mem_dict.values())
    
    with open(MEMORY_FILE, "w") as f:
        json.dump(final_output, f, indent=4)
            
    with open(GRAPH_FILE, "w") as f:
        json.dump(json_graph.node_link_data(G), f, indent=4)
    
    print(f"✅ Update Complete. {len(mem_dict)} units now in memory.")

if __name__ == "__main__":
    run_lumis(os.getenv("REPO_URL"))