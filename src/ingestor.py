import os
from tree_sitter_language_pack import get_parser
from src.services import get_llm_completion, get_embedding, generate_footprint

def get_code_data(file_path):
    ext = os.path.splitext(file_path)[1].replace('.', '').lower()
    extension_map = {"js": "javascript", "ts": "typescript", "py": "python", "rs": "rust"}
    
    if ext not in extension_map: return []
    parser = get_parser(extension_map[ext])
    if not parser: return []

    try:
        with open(file_path, "rb") as f:
            content = f.read()
            tree = parser.parse(content)
        
        results = []
        def walk(node):
            if node.type in ["function_definition", "method_definition", "function_declaration"]:
                name_node = node.child_by_field_name('name')
                func_name = content[name_node.start_byte:name_node.end_byte].decode('utf-8') if name_node else "anonymous"
                func_body = content[node.start_byte:node.end_byte].decode('utf-8')
                
                calls = []
                def find_calls(n):
                    if n.type in ["call", "call_expression"]:
                        calls.append(content[n.start_byte:n.end_byte].decode('utf-8'))
                    for child in n.children: find_calls(child)
                
                find_calls(node)
                results.append({"name": func_name, "code": func_body, "calls": list(set(calls))})

            for child in node.children: walk(child)

        walk(tree.root_node)
        return results
    except Exception as e:
        print(f"Parsing error: {e}")
        return []

def enrich_block(code_block, unit_name):
    system_msg = """You are a technical code analyst.
    Your task is to summarize the core logic of the provided code block in one clear, high-level sentence.

    STRICT RULES:
    1. If the code is purely boilerplate (e.g., just imports, an empty class/function, or standard setup code with no logic), return exactly: SKIP
    2. If the context is weak or the code is complex, DO NOT skip. Instead, describe what the code appears to be doing based on the function name, variables, and structure. 
    3. Focus on the 'Why' and 'What', not the line-by-line 'How'.
    4. Be concise. One sentence only."""
    # Pass both the name and the code for better context
    summary = get_llm_completion(system_msg, f"Function Name: {unit_name}\nCode:\n{code_block}")
    
    if not summary or "SKIP" in summary.upper():
        return None
    
    return {
        "summary": summary,
        "embedding": get_embedding(code_block),
        "footprint": generate_footprint(code_block)
    }