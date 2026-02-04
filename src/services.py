import os
from openai import OpenAI
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

# API configuration
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPEN_ROUTER"),
)

# The embedding model is loaded into memory once
embed_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_embedding(text):
    """Generates a vector for any given text."""
    return embed_model.encode(text).tolist()

def get_llm_completion(system_prompt, user_prompt, temperature=0.2):
    """Standard wrapper for OpenRouter API calls."""
    try:
        completion = client.chat.completions.create(
            extra_body={"reasoning": {"enabled": True}},
            model="stepfun/step-3.5-flash:free",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Service Error: {e}")
        return None