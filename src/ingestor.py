import os
from openai import OpenAI
from tree_sitter_language_pack import get_parser
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from src.services import get_llm_completion, get_embedding

load_dotenv()

# --- Setup AI ---
client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=os.getenv("OPEN_ROUTER"),
)
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_code_data(file_path):
    """Extracts function names, their code, and what they call."""
    ext = os.path.splitext(file_path)[1].replace('.', '').lower()
    extension_map = {"js": "javascript",
                    "ts": "typescript",
                    "py": "python",
                    "rs": "rust",
                    }
    if ext not in extension_map:
        return []
    
    lang_name = extension_map.get(ext, ext)
    
    parser = get_parser(lang_name)
    if not parser: return []

    try:
        with open(file_path, "rb") as f:
            content = f.read()
            tree = parser.parse(content)
        
        results = []
        
        def walk(node, current_func=None):
            # 1. Identify Function Definitions
            if node.type in ["function_definition", "method_definition", "function_declaration"]:
                name_node = node.child_by_field_name('name')
                func_name = content[name_node.start_byte:name_node.end_byte].decode('utf-8') if name_node else "anonymous"
                
                func_body = content[node.start_byte:node.end_byte].decode('utf-8')
                
                calls = []
                def find_calls(n):
                    if n.type == "call":
                        calls.append(content[n.start_byte:n.end_byte].decode('utf-8'))
                    for child in n.children: find_calls(child)
                
                find_calls(node)
                
                results.append({
                    "name": func_name,
                    "code": func_body,
                    "calls": list(set(calls))
                })

            for child in node.children:
                walk(child)

        walk(tree.root_node)
        return results
    except:
        return []

def enrich_block(code_block):
    """Summarizes with a SKIP logic to avoid junk data."""
    system_msg = "Summarize logic in one sentence. If boilerplate or empty, return: SKIP"
    
    summary = get_llm_completion(system_msg, f"Analyze: {code_block}")
    
    if not summary or "SKIP" in summary.upper():
        return None
    
    embedding = get_embedding(code_block)
    return {"summary": summary, "embedding": embedding}