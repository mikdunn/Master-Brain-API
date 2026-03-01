from pathlib import Path

from math_logic_agent.indexing import IndexStore


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def test_incremental_rebuild_reuses_unchanged_files(tmp_path: Path) -> None:
    d = tmp_path / "docs"
    d.mkdir()

    a = d / "a.txt"
    b = d / "b.txt"
    _write(a, "Singular value decomposition is useful for least squares.")
    _write(b, "Eigenvectors and eigenvalues.")

    index_path = tmp_path / "idx.pkl"

    store1, summary1 = IndexStore.build_from_directory(
        input_dir=d,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
    )
    store1.save(index_path)

    assert summary1.total_files == 2
    assert summary1.changed_files == 2
    assert summary1.reused_files == 0

    store2, summary2 = IndexStore.build_from_directory(
        input_dir=d,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
    )
    assert summary2.total_files == 2
    assert summary2.changed_files == 0
    assert summary2.reused_files == 2
    assert len(store2.chunks) == len(store1.chunks)

    _write(b, "Eigenvalues and PCA are related through covariance.")
    store3, summary3 = IndexStore.build_from_directory(
        input_dir=d,
        index_path=index_path,
        incremental=True,
        cloud_rerank=False,
    )
    assert summary3.changed_files == 1
    assert summary3.reused_files == 1
    assert len(store3.chunks) > 0
