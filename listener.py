import os
import json
import networkx as nx
from flask import Flask, request, jsonify
from git import Repo
from networkx.readwrite import json_graph
import threading
from src.ingestor import get_code_data, enrich_block

app = Flask(__name__)

# CONFIG
REPO_URL = os.getenv("REPO_URL")
TEMP_PATH = "temp_project"
MEMORY_FILE = "memory/lumis_memory.json"
GRAPH_FILE = "memory/lumis_graph.json"

def run_selective_sync(commit_id):
    print(f"🔄 Syncing Commit: {commit_id}")
    
    # 1. Load existing memory
    mem_dict = {}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
            # Filter out the metadata entry to build the dict
            mem_dict = {item["id"]: item for item in data if "id" in item}

    # 2. Update Local Repo
    if os.path.exists(TEMP_PATH):
        repo = Repo(TEMP_PATH)
        repo.remotes.origin.pull()
    else:
        Repo.clone_from(REPO_URL, TEMP_PATH)

    # 3. Process Deltas
    new_memory_dict = {}
    for root, _, files in os.walk(TEMP_PATH):
        if ".git" in root: continue
        for file in files:
            if not file.endswith(('.py', '.js', '.ts')): continue
            f_path = os.path.join(root, file)
            rel_path = os.path.relpath(f_path, TEMP_PATH)
            
            for unit in get_code_data(f_path):
                node_id = f"{rel_path}::{unit['name']}"
                from src.services import generate_footprint
                current_hash = generate_footprint(unit["code"])

                if node_id in mem_dict and mem_dict[node_id].get("footprint") == current_hash:
                    new_memory_dict[node_id] = mem_dict[node_id]
                else:
                    print(f"✨ Updating {node_id}")
                    intel = enrich_block(unit["code"])
                    if intel:
                        new_memory_dict[node_id] = {**intel, "id": node_id, "calls": unit["calls"]}

    # 4. Save with Metadata (including the last commit ID)
    G = nx.DiGraph()
    final_output = [{"last_commit": commit_id}] # Metadata entry
    
    for node_id, data in new_memory_dict.items():
        final_output.append(data)
        G.add_node(node_id, summary=data['summary'])
        for call in data.get('calls', []): G.add_edge(node_id, call)

    with open(MEMORY_FILE, "w") as f: json.dump(final_output, f, indent=4)
    with open(GRAPH_FILE, "w") as f: json.dump(json_graph.node_link_data(G), f, indent=4)
    print(f"✅ Sync Complete for {commit_id}")

@app.route('/', methods=['GET'])
def home():
    # Try to get the last commit and count of functions
    last_commit = "None"
    unit_count = 0
    
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                data = json.load(f)
                if data:
                    last_commit = data[0].get("last_commit", "Unknown")
                    unit_count = len(data) - 1 # Subtract 1 for the metadata entry
        except:
            pass

    # This creates a simple HTML dashboard
    return f"""
    <html>
        <head><title>Lumis Status</title></head>
        <body style="font-family: sans-serif; padding: 40px; line-height: 1.6;">
            <h1 style="color: #2c3e50;">🤖 Lumis Digital Twin: Active</h1>
            <hr>
            <p><strong>Status:</strong> <span style="color: green;">Online and Listening</span></p>
            <p><strong>Last Synced Commit:</strong> <code>{last_commit}</code></p>
            <p><strong>Knowledge Units Indexed:</strong> {unit_count}</p>
            <p><strong>Webhook Endpoint:</strong> <code>/webhook</code> (POST only)</p>
            <br>
            <div style="background: #f4f4f4; padding: 15px; border-radius: 8px;">
                <small>To trigger a sync manually, push code to your GitHub repository.</small>
            </div>
        </body>
    </html>
    """

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.json
    new_commit = payload.get('after') # GitHub sends the new commit ID here
    
    # Check current memory for the last processed commit
    last_processed = None
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            data = json.load(f)
            if data and "last_commit" in data[0]:
                last_processed = data[0]["last_commit"]

    if new_commit == last_processed:
        return jsonify({"status": "already_synced"}), 200

    threading.Thread(target=run_selective_sync, args=(new_commit,)).start()
    return jsonify({"status": "sync_started", "commit": new_commit}), 202

if __name__ == "__main__":
    app.run(port=5000)