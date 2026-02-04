import json
import os
import numpy as np
import networkx as nx
from networkx.readwrite import json_graph
from src.services import get_embedding, get_llm_completion

# Configuration
MEMORY_FILE = "memory/lumis_memory.json"
GRAPH_FILE = "memory/lumis_graph.json"

def load_knowledge():
    if not os.path.exists(MEMORY_FILE) or not os.path.exists(GRAPH_FILE):
        print("Error: Memory files not found. Run main.py first.")
        return None, None
    
    with open(MEMORY_FILE, 'r') as f:
        memory = json.load(f)
    with open(GRAPH_FILE, 'r') as f:
        data = json.load(f)
        graph = json_graph.node_link_graph(data)
    
    return memory, graph

def find_context(query, memory, top_k=3):
    query_vec = np.array(get_embedding(query))
    similarities = []
    
    for unit in memory:
        if "embedding" not in unit: continue
        unit_vec = np.array(unit["embedding"])
        sim = np.dot(query_vec, unit_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(unit_vec))
        similarities.append((sim, unit))
    
    similarities.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in similarities[:top_k]]

def get_graph_context(node_id, G):
    """Explores the neighborhood of a code unit."""
    if node_id not in G:
        return ""
    
    callers = list(G.predecessors(node_id))
    callees = list(G.successors(node_id))
    
    context = f"\n- Relationships for {node_id}:"
    if callers:
        context += f"\n  * Called by: {', '.join(callers)}"
    if callees:
        context += f"\n  * Calls these functions: {', '.join(callees)}"
    return context

def ask_twin(query):
    memory, graph = load_knowledge()
    if not memory: return

    # 1. Semantic Search
    context_units = find_context(query, memory)
    
    # 2. Build Context with Graph Traces
    full_context_str = ""
    for u in context_units:
        unit_info = f"File/Unit: {u['id']}\nSummary: {u['summary']}"
        # Add the 'Trace' information
        relationship_info = get_graph_context(u['id'], graph)
        full_context_str += unit_info + relationship_info + "\n\n"

    # 3. Prompting
    system_prompt = (
        "You are Lumis, the Digital Twin of this codebase. "
        "Use the provided summaries and relationship traces to answer. "
        "Pay attention to how functions call each other to explain the impact of changes."
    )
    
    user_prompt = f"Context from codebase:\n{full_context_str}\n\nQuestion: {query}"

    return get_llm_completion(system_prompt, user_prompt)

if __name__ == "__main__":
    print("--- Lumis Digital Twin ---")
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ['exit', 'quit']: break
        print("\nLumis is tracing the graph...")
        print(f"\nLumis: {ask_twin(user_input)}")