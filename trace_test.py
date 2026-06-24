import os
import time
from dotenv import load_dotenv

load_dotenv()
# Explicitly map the key and enable tracing
if "LANGSMITH_API_KEY" in os.environ:
    os.environ["LANGCHAIN_API_KEY"] = os.environ["LANGSMITH_API_KEY"]
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "marketpulse-ai"

from langchain_groq import ChatGroq

print("Starting test trace...")
print("Project:", os.environ.get("LANGCHAIN_PROJECT"))
print("API Key set:", bool(os.environ.get("LANGCHAIN_API_KEY")))

llm = ChatGroq(model="llama-3.1-8b-instant")
response = llm.invoke("Please say the exact phrase: LangSmith Trace Successful!")
print("LLM replied:", response.content)

print("Waiting 5 seconds to ensure trace uploads to LangSmith...")
time.sleep(5)
print("Trace test complete!")
