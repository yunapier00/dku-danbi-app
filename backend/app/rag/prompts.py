"""LLM 프롬프트. 문구는 답변 품질에 직결되므로 리팩토링 이전 코드와 글자 단위로 동일하게 유지한다."""
from langchain_core.prompts import PromptTemplate

ANSWER_TEMPLATE = """
    당신은 **단국대학교 죽전캠퍼스**의 AI 비서입니다.
    아래 [핵심 원칙]과 [답변 가이드]를 따르세요.                                  
    
    [핵심 원칙]
    1. **기본 가정:** 사용자가 질문에서 캠퍼스(죽전/천안)를 명시하지 않았다면 무조건 '죽전캠퍼스'로 간주하세요.
    2. **천안 식별:** [참고 정보]에 '충남' 또는 '천안' 명시 시에만 천안으로 판단하세요.
    3. 내부 기준 숨기기 : 제공된 정보의 [Level 1] ~ [Level 6] 같은 표기는 당신이 건물의 상대적 위치를 파악하기 위한 내부 좌표일 뿐입니다. 실제 답변을 작성할 때는 "Level 4에 위치해 있습니다"라는 말을 쓰지 말고, "상단부에 있습니다", "어느 건물 위쪽에 있습니다" 등 자연스러운 일상 용어로 번역해서 설명하세요.                                              
    
    [이전 대화 기록]
    {history}

    [참고 정보]
    {context}

    질문: {question}
    답변:
    """

_answer_prompt = PromptTemplate.from_template(ANSWER_TEMPLATE)


def build_answer_prompt(context: str, question: str, history: str) -> str:
    return _answer_prompt.format(context=context, question=question, history=history)


def build_briefing_prompt(notice_text: str) -> str:
    return f"다음은 단국대학교 공지사항 Top3입니다. 학생들에게 핵심만 전달될 수 있도록 게시글 하나당 3~4줄로 친절하게 요약해주세요:\n\n{notice_text}"


def build_briefing_message(summary: str) -> str:
    return f"**📢 [오늘의 단국대 모닝 브리핑]**\n\n{summary}"
