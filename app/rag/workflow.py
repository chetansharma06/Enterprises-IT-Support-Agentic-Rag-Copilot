import logging
import random
import time
from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_tavily import TavilySearch
from langgraph.graph import StateGraph, START, END
from app.core.config import get_settings
from app.core.network import external_call
from app.rag.state import AgentState, RouteDecision, EvidenceGrade
from app.rag.vectorstore import get_retriever

logger = logging.getLogger(__name__)
settings = get_settings()

_llms: dict = {}
_web_search = None


def _build_llm(model: str):
    """Create (and cache) one Gemini client per model name."""
    if model not in _llms:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is missing")
        _llms[model] = ChatGoogleGenerativeAI(
            model=model,
            temperature=0,
            api_key=settings.gemini_api_key,
            max_retries=0,  # retries are handled in invoke_gemini below
        )
    return _llms[model]


def _fallback_model() -> str:
    # If you add `gemini_fallback_model` to config.py it will be used,
    # otherwise this default backup model is used.
    return getattr(settings, "gemini_fallback_model", "") or "gemini-2.5-flash"


def llm():
    """Plain LLM. If the primary model fails, the backup model is tried."""
    primary = _build_llm(settings.gemini_model)
    backup = _fallback_model()
    if backup and backup != settings.gemini_model:
        return primary.with_fallbacks([_build_llm(backup)])
    return primary


def structured_llm(schema):
    """Structured-output LLM (router / graders) with a backup model."""
    primary = _build_llm(settings.gemini_model).with_structured_output(schema, method="json_mode")
    backup = _fallback_model()
    if backup and backup != settings.gemini_model:
        return primary.with_fallbacks(
            [_build_llm(backup).with_structured_output(schema, method="json_mode")]
        )
    return primary


_TRANSIENT_WORDS = (
    "503",
    "UNAVAILABLE",
    "HIGH DEMAND",
    "429",
    "RESOURCE_EXHAUSTED",
    "DEADLINE_EXCEEDED",
)


def _is_transient(exc: Exception) -> bool:
    text = str(exc).upper()
    return any(word in text for word in _TRANSIENT_WORDS)


def invoke_gemini(runnable, prompt, max_attempts: int = 4):
    """Call Gemini with retry + exponential backoff for temporary errors (503/429)."""
    for attempt in range(1, max_attempts + 1):
        try:
            return external_call(
                "generativelanguage.googleapis.com",
                "calling Google Gemini",
                lambda: runnable.invoke(prompt),
            )
        except Exception as exc:
            if attempt == max_attempts or not _is_transient(exc):
                raise
            delay = min(2 ** attempt, 10) + random.uniform(0, 1)  # ~2s, 4s, 8s
            logger.warning(
                "Gemini busy (attempt %s/%s), retrying in %.1fs", attempt, max_attempts, delay
            )
            time.sleep(delay)


def web_search_tool():
    global _web_search
    if _web_search is None:
        if not settings.tavily_api_key:
            raise RuntimeError("TAVILY_API_KEY is missing")
        _web_search = TavilySearch(
            tavily_api_key=settings.tavily_api_key,
            max_results=5,
            topic="general",
            include_answer=True,
            include_raw_content=False,
        )
    return _web_search

def add_trace(state: AgentState, message: str):
    return [*state.get("trace", []), message]

def route_question(state: AgentState):
    router = structured_llm(RouteDecision)
    decision = invoke_gemini(router, f"""
You route messages for an enterprise IT support assistant.
Use kb for questions about company IT policies, VPN, password reset, MFA, laptop setup,
software access, security, email, devices, troubleshooting, or technology support.
Use direct only for greetings, thanks, or casual chat that needs no company knowledge.
Question: {state['question']}
Return valid JSON like {{"route":"kb"}}.
""")
    return {"source_used": decision.route, "trace": add_trace(state, f"Router → {decision.route.upper()}")}

def route_after_router(state: AgentState) -> Literal["retrieve_kb", "direct_answer"]:
    return "retrieve_kb" if state["source_used"] == "kb" else "direct_answer"

def retrieve_kb(state: AgentState):
    docs = get_retriever().invoke(state["current_query"])
    return {"kb_docs": docs, "trace": add_trace(state, f"Private KB retrieval → {len(docs)} chunks")}

def grade_kb(state: AgentState):
    grader = structured_llm(EvidenceGrade)
    context = "\n\n".join(f"Source: {d.metadata.get('source','unknown')}\n{d.page_content}" for d in state["kb_docs"])
    grade = invoke_gemini(grader, f"""
You grade evidence for an enterprise IT support assistant.
Question: {state['question']}
Private company KB evidence:\n{context}
Return good only if the evidence is sufficient to answer confidently and specifically.
Otherwise return weak. JSON: {{"grade":"good"}} or {{"grade":"weak"}}.
""")
    return {"kb_grade": grade.grade, "trace": add_trace(state, f"KB evidence grade → {grade.grade.upper()}")}

def after_kb(state: AgentState) -> Literal["generate_from_kb", "search_web"]:
    return "generate_from_kb" if state["kb_grade"] == "good" else "search_web"

def search_web(state: AgentState):
    result = external_call("api.tavily.com", "calling Tavily search", lambda: web_search_tool().invoke({"query": state["current_query"]}))
    lines, citations = [], []
    if isinstance(result, dict):
        if result.get("answer"):
            lines.append("Search answer: " + result["answer"])
        for item in result.get("results", []):
            title, url, content = item.get("title", ""), item.get("url", ""), item.get("content", "")
            lines.append(f"Title: {title}\nURL: {url}\nContent: {content}")
            citations.append({"title": title or url, "url": url, "type": "web"})
    else:
        lines.append(str(result))
    return {
        "web_results": "\n\n".join(lines),
        "citations": citations,
        "source_used": "web",
        "trace": add_trace(state, "Web fallback → Tavily search"),
    }

def grade_web(state: AgentState):
    grader = structured_llm(EvidenceGrade)
    grade = invoke_gemini(grader, f"""
Question: {state['question']}
Web evidence:\n{state['web_results']}
Return good if the evidence is sufficient and directly relevant; otherwise weak.
Return valid JSON like {{"grade":"good"}}.
""")
    return {"web_grade": grade.grade, "trace": add_trace(state, f"Web evidence grade → {grade.grade.upper()}")}

def after_web(state: AgentState) -> Literal["generate_from_web", "rewrite_query", "insufficient"]:
    if state["web_grade"] == "good":
        return "generate_from_web"
    if state["retry_count"] < settings.max_retries:
        return "rewrite_query"
    return "insufficient"

def rewrite_query(state: AgentState):
    rewritten = invoke_gemini(llm(), f"""
Rewrite this IT support question for better private knowledge retrieval and vendor web search.
Preserve intent, add useful technical keywords, do not answer, return only the query.
Question: {state['question']}
""").content.strip()
    return {
        "current_query": rewritten,
        "retry_count": state["retry_count"] + 1,
        "trace": add_trace(state, f"Query rewrite → {rewritten}"),
    }

def generate_from_kb(state: AgentState):
    context = "\n\n".join(f"[Source: {d.metadata.get('source','unknown')}]\n{d.page_content}" for d in state["kb_docs"])
    answer = invoke_gemini(llm(), f"""
You are an enterprise IT support copilot. Answer ONLY from the private company KB below.
Be concise, actionable, and safe. If steps are present, present them clearly.
Do not invent policy details. Mention that the answer is based on the company's private knowledge base.
Question: {state['question']}\n\nPrivate KB:\n{context}
""").content
    citations = []
    seen = set()
    for d in state["kb_docs"]:
        src = d.metadata.get("source", "Private KB")
        if src not in seen:
            seen.add(src)
            citations.append({"title": src.split("/")[-1], "url": "", "type": "private_kb"})
    return {"answer": answer, "source_used": "private_kb", "citations": citations, "trace": add_trace(state, "Answer generation → PRIVATE KB")}

def generate_from_web(state: AgentState):
    answer = invoke_gemini(llm(), f"""
You are an enterprise IT support copilot. The private company KB was insufficient.
Answer ONLY from the web evidence below. Clearly say this is external web information and may need IT validation before changing company-managed systems.
Question: {state['question']}\n\nWeb evidence:\n{state['web_results']}
""").content
    return {"answer": answer, "source_used": "web_search", "trace": add_trace(state, "Answer generation → WEB SEARCH")}

def direct_answer(state: AgentState):
    answer = invoke_gemini(llm(), f"Respond briefly and naturally to: {state['question']}").content
    return {"answer": answer, "source_used": "direct", "trace": add_trace(state, "Direct response → no retrieval")}

def insufficient(state: AgentState):
    return {
        "answer": "I couldn't find enough reliable evidence in the company knowledge base or external search to answer confidently. Please contact the IT help desk or provide more details.",
        "source_used": "insufficient_evidence",
        "trace": add_trace(state, "Stopped → insufficient reliable evidence"),
    }

def build_graph():
    graph = StateGraph(AgentState)
    for name, fn in {
        "route_question": route_question,
        "retrieve_kb": retrieve_kb,
        "grade_kb": grade_kb,
        "search_web": search_web,
        "grade_web": grade_web,
        "rewrite_query": rewrite_query,
        "generate_from_kb": generate_from_kb,
        "generate_from_web": generate_from_web,
        "direct_answer": direct_answer,
        "insufficient": insufficient,
    }.items():
        graph.add_node(name, fn)

    graph.add_edge(START, "route_question")
    graph.add_conditional_edges("route_question", route_after_router, {
        "retrieve_kb": "retrieve_kb", "direct_answer": "direct_answer"
    })
    graph.add_edge("retrieve_kb", "grade_kb")
    graph.add_conditional_edges("grade_kb", after_kb, {
        "generate_from_kb": "generate_from_kb", "search_web": "search_web"
    })
    graph.add_edge("search_web", "grade_web")
    graph.add_conditional_edges("grade_web", after_web, {
        "generate_from_web": "generate_from_web", "rewrite_query": "rewrite_query", "insufficient": "insufficient"
    })
    graph.add_edge("rewrite_query", "retrieve_kb")
    graph.add_edge("generate_from_kb", END)
    graph.add_edge("generate_from_web", END)
    graph.add_edge("direct_answer", END)
    graph.add_edge("insufficient", END)
    return graph.compile()

agent_graph = build_graph()

def ask(question: str):
    initial: AgentState = {
        "question": question,
        "current_query": question,
        "kb_docs": [],
        "web_results": "",
        "kb_grade": "",
        "web_grade": "",
        "answer": "",
        "source_used": "",
        "retry_count": 0,
        "trace": [],
        "citations": [],
    }
    return agent_graph.invoke(initial)