from emporio.policies import ingest
from emporio.policies.retriever import tokenize


def _chunks():
    return ingest.build()


def test_expected_ids_present():
    ids = {chunk.id for chunk in _chunks()}
    expected = {"1.2", "2", "3.1", "4.1", "4.2", "5.1", "5.3", "6.2", "7.1", "8.2"}
    assert expected <= ids


def test_ids_unique_and_no_empty_text():
    chunks = _chunks()
    ids = [chunk.id for chunk in chunks]
    assert len(ids) == len(set(ids))
    assert all(chunk.text.strip() for chunk in chunks)


def test_no_page_noise():
    for chunk in _chunks():
        assert "Página " not in chunk.text


def test_greeting_list_item_is_not_a_section():
    ids = {chunk.id for chunk in _chunks()}
    # "1. Saudação:" é item do fluxo 7.2, não pode virar a seção "1".
    chunk_72 = next(chunk for chunk in _chunks() if chunk.id == "7.2")
    assert "Saudação" in chunk_72.text
    assert "7.2" in ids


def test_tokenize_shares_stem_devol():
    assert "devol" in tokenize("devolução")
    assert "devol" in tokenize("devolver")
