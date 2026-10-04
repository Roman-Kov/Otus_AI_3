from api_agent.cli import is_contract_answer


def test_contract_answer_accepted():
    assert is_contract_answer("Status: success\nAction: создан")
    assert is_contract_answer("  Status: error\nAction: нет")


def test_raw_answer_rejected():
    assert not is_contract_answer("Готово! Пользователь создан.")
    assert not is_contract_answer("")
