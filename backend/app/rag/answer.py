from app.rag.llm import extract_text
from app.rag.prompts import build_answer_prompt


def generate_answer(llm, context: str, query: str, history: str) -> str:
    response = llm.invoke(build_answer_prompt(context=context, question=query, history=history))
    return extract_text(response)
