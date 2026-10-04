import logging
import sys

from .agent import build_agent

logger = logging.getLogger("api_agent.cli")


def is_contract_answer(text: str) -> bool:
    return text.lstrip().startswith("Status:")


def run(query: str) -> str:
    agent = build_agent()
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    return str(result["messages"][-1].content)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("agent.log", encoding="utf-8"),
        ],
    )
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Использование: python main.py "<запрос на естественном языке>"')
        raise SystemExit(1)
    answer = run(sys.argv[1])
    print(answer if is_contract_answer(answer) else f"[raw] {answer}")
