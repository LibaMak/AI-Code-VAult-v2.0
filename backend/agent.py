# backend/agent.py
# Agentic AI layer for AI Code Vault 2.0
# Drop this file into the backend/ folder

import os
import json
from dotenv import load_dotenv

# Load .env from project root so GROQ_API_KEY is available when running Streamlit
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
from groq import Groq


client = None
MODEL = "llama-3.3-70b-versatile"


def _extract_retry_hint(error_text: str) -> str:
    """Pull a human-friendly retry hint out of a provider error string."""
    marker = "Please try again in "
    if marker in error_text:
        tail = error_text.split(marker, 1)[1]
        return tail.split(".", 1)[0].strip()
    return "a few minutes"


def _build_provider_fallback(user_message: str, error_text: str) -> str:
    """Return a safe, always-on fallback answer when Groq is unavailable."""
    if "rate_limit_exceeded" in error_text or "Error code: 429" in error_text:
        retry_hint = _extract_retry_hint(error_text)
        return (
            f"The AI model is currently rate-limited, so I can't use it right now. "
            f"Please try again in about {retry_hint}."
        )

    if "model_decommissioned" in error_text or "Error code: 400" in error_text:
        return (
            "The configured AI model is no longer supported by the provider. "
            "I can still help with a direct summary or troubleshoot the setup if you want."
        )

    return (
        "I couldn't reach the AI provider just now, so I can't generate a model-based response. "
        "Please try again shortly or share the specific question and I can help narrow it down."
    )


def get_client():
    """Create a Groq client lazily so the module can be imported without an API key."""
    global client
    if client is not None:
        return client

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    try:
        client = Groq(api_key=api_key)
    except Exception:
        client = None
    return client

# ══════════════════════════════════════════════════════════════════════════════
#  TOOL DEFINITIONS  (tell the LLM what tools exist)
# ══════════════════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "search_vault",
        "description": "Search the indexed code/document vault using semantic + keyword hybrid search. Use this when the user asks a question about code, files, or documents stored in the vault.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query to look up in the vault."},
                "top_k": {"type": "integer", "description": "Number of results to return (default 5).", "default": 5}
            },
            "required": ["query"]
        }
    },
    {
        "name": "summarize_document",
        "description": "Summarize a specific document or file from the vault. Use this when the user asks for a summary, overview, or TL;DR of a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The name of the file to summarize."}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "generate_quiz",
        "description": "Generate quiz questions from a document or topic in the vault. Use this when the user asks for a quiz, test questions, or wants to test knowledge.",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The topic or filename to generate quiz questions from."},
                "num_questions": {"type": "integer", "description": "Number of quiz questions to generate (default 5).", "default": 5}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "extract_key_points",
        "description": "Extract key points, tables, or important information from a document. Use this when the user asks for key points, bullet points, main ideas, or tables.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "The name of the file to extract key points from."}
            },
            "required": ["filename"]
        }
    },
    {
        "name": "analyze_and_recommend",
        "description": "Analyze code or documents and provide recommendations, insights, or improvements. Use this when the user asks for analysis, review, recommendations, or suggestions.",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "The filename or topic to analyze."},
                "analysis_type": {"type": "string", "description": "Type of analysis: 'code_review', 'security', 'performance', or 'general'.", "enum": ["code_review", "security", "performance", "general"]}
            },
            "required": ["target", "analysis_type"]
        }
    },
    {
        "name": "repo_overview",
        "description": "Create a high-level overview of the most relevant files for a repository or feature. Use this when the user asks for architecture, structure, or a project summary.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A broad topic or repository query to inspect."}
            },
            "required": ["query"]
        }
    }
]


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL EXECUTOR  (calls your existing backend functions)
# ══════════════════════════════════════════════════════════════════════════════

def _run_search(backend, query: str, top_k: int = 5):
    """Use the app's existing hybrid search function when available."""
    search_fn = backend.get("run_hybrid_search") or backend.get("search_vault")
    if callable(search_fn):
        try:
            return search_fn(query, top_k=top_k)
        except TypeError:
            return search_fn(query)
    return None


def execute_tool(tool_name: str, tool_args: dict, backend) -> str:
    """
    Routes tool calls to your existing backend functions.
    'backend' is the loaded backend module dict from streamlit_app.py.
    """
    try:
        if tool_name == "search_vault":
            query = tool_args.get("query", "")
            top_k = tool_args.get("top_k", 5)
            results = _run_search(backend, query, top_k=top_k)
            if results:
                formatted = []
                for i, r in enumerate(results, 1):
                    if isinstance(r, dict):
                        chunk = r.get("snippet", r.get("content", r.get("chunk", str(r))))
                        source = r.get("name", r.get("filename", r.get("source", "unknown")))
                        score = r.get("score", r.get("similarity", "N/A"))
                    else:
                        chunk = str(r)
                        source = "unknown"
                        score = "N/A"
                    formatted.append(f"[{i}] Source: {source} | Score: {score}\n{chunk}")
                return "\n\n".join(formatted)
            return "No results found in the vault for that query."

        elif tool_name == "summarize_document":
            filename = tool_args.get("filename", "")
            results = _run_search(backend, f"summarize {filename}", top_k=8)
            if results:
                chunks = " ".join([
                    r.get("snippet", r.get("content", r.get("chunk", ""))) if isinstance(r, dict) else str(r)
                    for r in results
                ])
                groq_client = get_client()
                if groq_client is None:
                    return chunks[:1000]
                resp = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": "You are a document summarizer. Summarize the following content concisely."},
                        {"role": "user", "content": f"Summarize this content from {filename}:\n\n{chunks[:3000]}"}
                    ],
                    max_tokens=500
                )
                return resp.choices[0].message.content
            return f"Could not retrieve content for {filename}."

        elif tool_name == "generate_quiz":
            topic = tool_args.get("topic", "")
            num_q = tool_args.get("num_questions", 5)
            results = _run_search(backend, topic, top_k=6)
            if results:
                chunks = " ".join([
                    r.get("snippet", r.get("content", r.get("chunk", ""))) if isinstance(r, dict) else str(r)
                    for r in results
                ])
                groq_client = get_client()
                if groq_client is None:
                    return chunks[:1000]
                resp = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": "You are a quiz generator. Create clear multiple-choice questions with answers."},
                        {"role": "user", "content": f"Generate {num_q} quiz questions about '{topic}' based on:\n\n{chunks[:3000]}"}
                    ],
                    max_tokens=800
                )
                return resp.choices[0].message.content
            return f"Could not generate quiz for topic: {topic}."

        elif tool_name == "extract_key_points":
            filename = tool_args.get("filename", "")
            results = _run_search(backend, filename, top_k=8)
            if results:
                chunks = " ".join([
                    r.get("snippet", r.get("content", r.get("chunk", ""))) if isinstance(r, dict) else str(r)
                    for r in results
                ])
                groq_client = get_client()
                if groq_client is None:
                    return chunks[:1000]
                resp = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": "Extract the most important key points, facts, and any tables as bullet points."},
                        {"role": "user", "content": f"Extract key points from {filename}:\n\n{chunks[:3000]}"}
                    ],
                    max_tokens=600
                )
                return resp.choices[0].message.content
            return f"Could not extract key points from {filename}."

        elif tool_name == "analyze_and_recommend":
            target = tool_args.get("target", "")
            analysis_type = tool_args.get("analysis_type", "general")
            results = _run_search(backend, target, top_k=6)
            if results:
                chunks = " ".join([
                    r.get("snippet", r.get("content", r.get("chunk", ""))) if isinstance(r, dict) else str(r)
                    for r in results
                ])
                prompts = {
                    "code_review": "Review this code for bugs, readability, and best practices. Give specific recommendations.",
                    "security": "Analyze this code for security vulnerabilities and suggest fixes.",
                    "performance": "Analyze this code for performance issues and suggest optimizations.",
                    "general": "Provide a general analysis with actionable recommendations."
                }
                system_prompt = prompts.get(analysis_type, prompts["general"])
                groq_client = get_client()
                if groq_client is None:
                    return chunks[:1000]
                resp = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Analyze '{target}':\n\n{chunks[:3000]}"}
                    ],
                    max_tokens=800
                )
                return resp.choices[0].message.content
            return f"Could not analyze {target}."

        elif tool_name == "repo_overview":
            query = tool_args.get("query", "project overview")
            results = _run_search(backend, query, top_k=8)
            if results:
                formatted_results = []
                for item in results:
                    if isinstance(item, dict):
                        formatted_results.append(
                            f"File: {item.get('name', 'unknown')}\nScore: {item.get('score', 'N/A')}\nSnippet: {item.get('snippet', '')}"
                        )
                    else:
                        formatted_results.append(str(item))
                overview_text = "\n\n".join(formatted_results)
                groq_client = get_client()
                if groq_client is None:
                    return overview_text[:1400]
                resp = groq_client.chat.completions.create(
                    model=MODEL,
                    messages=[
                        {"role": "system", "content": "You are a software architect. Summarize the repository structure, main files, and likely responsibilities from the evidence."},
                        {"role": "user", "content": f"Create a concise repo overview from this evidence for: {query}\n\n{overview_text[:3500]}"}
                    ],
                    max_tokens=700
                )
                return resp.choices[0].message.content
            return f"Could not build a repo overview for: {query}."

        else:
            return f"Unknown tool: {tool_name}"

    except Exception as e:
        return f"Tool execution error ({tool_name}): {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN AGENT FUNCTION  (called from streamlit_app.py)
# ══════════════════════════════════════════════════════════════════════════════

def run_agent(user_message: str, chat_history: list, backend: dict) -> dict:
    """
    Runs the agentic loop for one user turn.

    Args:
        user_message  : The user's latest message string.
        chat_history  : List of previous {"role": ..., "content": ...} dicts.
        backend       : The backend module dict from streamlit_app.py load_backend().

    Returns:
        {
            "answer":  str,           # Final answer to show the user
            "steps":   list[dict],    # Agent reasoning steps for the UI expander
            "tools_used": list[str]   # Names of tools the agent chose to call
        }
    """

    system_prompt = """You are an intelligent AI assistant for the AI Code Vault — 
a platform for indexing and querying code repositories and documents.

You have access to the following tools when needed:
- search_vault: Search indexed files semantically
- summarize_document: Summarize a specific file
- generate_quiz: Generate quiz questions on a topic
- extract_key_points: Extract key points and tables from a file
- analyze_and_recommend: Analyze code/docs and give recommendations
- repo_overview: Get high-level repository overview

IMPORTANT: 
- Use tools ONLY when the user asks about code/documents in the vault or needs vault-specific analysis.
- For general knowledge questions, greetings, or requests that don't need vault data, answer directly WITHOUT tools.
- You can call multiple tools if needed to fully answer a question.
- After getting tool results, synthesize a clear, helpful answer.
- Always cite which files/sources your answer came from when using tools.
- If tools are not needed, answer the question directly and helpfully."""

    # Build messages: system + history + new user message
    if chat_history and chat_history[-1].get("role") == "user" and chat_history[-1].get("content") == user_message:
        chat_history = chat_history[:-1]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(chat_history[-6:])  # last 3 turns for context
    messages.append({"role": "user", "content": user_message})

    steps = []
    tools_used = []
    max_iterations = 5  # prevent infinite loops

    # ── Agentic loop ──────────────────────────────────────────────────────────
    for iteration in range(max_iterations):

        groq_client = get_client()
        if groq_client is None:
            return {
                "answer": "GROQ_API_KEY is not configured, so the agent cannot run tool-calling mode.",
                "steps": [],
                "tools_used": []
            }

        try:
            response = groq_client.chat.completions.create(
                model=MODEL,
                messages=messages,
                functions=TOOLS,
                function_call="auto",
                max_tokens=1000
            )
        except Exception as e:
            # Capture provider error including failed_generation hints
            err_text = str(e)
            fallback_answer = _build_provider_fallback(user_message, err_text)
            fallback_note = "AI provider is temporarily unavailable; used fallback response."
            if "rate_limit_exceeded" in err_text or "Error code: 429" in err_text:
                fallback_note = "AI provider is rate-limited; used fallback response."
            elif "model_decommissioned" in err_text or "Error code: 400" in err_text:
                fallback_note = "AI provider model is unavailable; used fallback response."
            steps.append({
                "iteration": iteration + 1,
                "type": "fallback",
                "content": fallback_note
            })
            return {
                "answer": fallback_answer,
                "steps": steps,
                "tools_used": tools_used
            }

        response_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason

        # ── No tool call → agent has its final answer ──────────────────────
        if finish_reason == "stop" or not response_message.tool_calls:
            final_answer = response_message.content or "I couldn't generate a response."
            steps.append({
                "iteration": iteration + 1,
                "type": "final_answer",
                "content": f"Agent produced final answer after {iteration + 1} iteration(s)."
            })
            return {
                "answer": final_answer,
                "steps": steps,
                "tools_used": tools_used
            }

        # ── Tool calls → execute each one ──────────────────────────────────
        tool_calls = response_message.tool_calls

        # Add assistant's tool-call message to history
        messages.append({
            "role": "assistant",
            "content": response_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in tool_calls
            ]
        })

        # Execute tools and collect results
        for tc in tool_calls:
            tool_name = tc.function.name
            try:
                tool_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                tool_args = {}

            tools_used.append(tool_name)

            # Log the step
            steps.append({
                "iteration": iteration + 1,
                "type": "tool_call",
                "tool": tool_name,
                "args": tool_args,
                "content": f"🔧 Calling **{tool_name}** with args: `{tool_args}`"
            })

            # Run the tool
            tool_result = execute_tool(tool_name, tool_args, backend)
            if tool_result is None:
                tool_result = ""
            # Ensure tool_result is a string and not excessively long
            if not isinstance(tool_result, str):
                try:
                    tool_result = str(tool_result)
                except Exception:
                    tool_result = "<non-string tool result>"
            if len(tool_result) > 32000:
                tool_result = tool_result[:32000] + "\n\n[TRUNCATED]"

            # Log result
            steps.append({
                "iteration": iteration + 1,
                "type": "tool_result",
                "tool": tool_name,
                "content": f"✅ **{tool_name}** returned {len(tool_result)} chars of results."
            })

            # Add tool result to messages so LLM can see it
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result
            })

    # If we exit the loop without a stop, use fallback LLM response (no tools)
    groq_client = get_client()
    if groq_client:
        try:
            fallback_response = groq_client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful AI assistant. Answer the user's question directly and concisely."},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=800
            )
            fallback_answer = fallback_response.choices[0].message.content or "I couldn't generate an answer."
            steps.append({
                "iteration": max_iterations,
                "type": "fallback",
                "content": "Agent reached max steps. Used fallback LLM response (no tools)."
            })
            return {
                "answer": fallback_answer,
                "steps": steps,
                "tools_used": tools_used
            }
        except Exception as e:
            fallback_text = f"Fallback error: {str(e)}"
            steps.append({
                "iteration": max_iterations,
                "type": "fallback_error",
                "content": fallback_text
            })
            return {
                "answer": "I couldn't generate a model response just now, but the app is still working. Please try again shortly.",
                "steps": steps,
                "tools_used": tools_used
            }
    
    return {
        "answer": "I couldn't complete the full agent loop, but the app is still working. Please try a more specific question.",
        "steps": steps,
        "tools_used": tools_used
    }
