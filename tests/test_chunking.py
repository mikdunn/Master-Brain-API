from math_logic_agent.chunking import chunk_documents, split_text
from math_logic_agent.models import RawDocument


def test_split_text_respects_max_chars() -> None:
    text = "A" * 2600
    chunks = split_text(text, max_chars=1000, overlap=100)
    assert len(chunks) >= 3
    assert all(len(c) <= 1000 for c in chunks)


def test_chunk_documents_generates_ids_and_tags() -> None:
    docs = [
        RawDocument(
            text="Theorem: SVD decomposes a matrix into singular vectors.",
            source="sample.pdf",
            page=2,
        )
    ]
    chunks = chunk_documents(docs)
    assert len(chunks) == 1
    assert chunks[0].chunk_id
    assert "theorem" in chunks[0].tags
    assert "svd" in chunks[0].tags


def test_chunk_documents_tags_tensor() -> None:
    docs = [
        RawDocument(
            text=(
                "We study tensor decomposition via CP and Tucker models "
                "(multilinear algebra)."
            ),
            source="tensor_notes.pdf",
            page=1,
        )
    ]
    chunks = chunk_documents(docs)
    assert len(chunks) == 1
    assert "tensor" in chunks[0].tags
