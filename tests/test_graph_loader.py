"""load_graph 동적 로더 단위 테스트."""

from __future__ import annotations

import pytest

from app.utils.langgraph_loader import load_graph


class TestLoadGraph:
    """load_graph 동적 로더 테스트."""

    def test_load_graph_from_src(self) -> None:
        """src/graph.py:graph 경로에서 그래프를 로드합니다."""
        graph = load_graph("./src/graph.py:graph")
        assert graph is not None
        assert hasattr(graph, "invoke")

    def test_invalid_format_raises(self) -> None:
        """콜론이 없는 경로는 ValueError를 발생시킵니다."""
        with pytest.raises(ValueError, match="형식이 잘못되었습니다"):
            load_graph("src/graph.py")

    def test_nonexistent_module_raises(self) -> None:
        """존재하지 않는 모듈은 ImportError를 발생시킵니다."""
        with pytest.raises(ImportError):
            load_graph("nonexistent.module:graph")

    def test_nonexistent_attribute_raises(self) -> None:
        """존재하지 않는 속성은 AttributeError를 발생시킵니다."""
        with pytest.raises(AttributeError):
            load_graph("./src/graph.py:nonexistent")

    def test_nonexistent_file_raises(self) -> None:
        """존재하지 않는 파일 경로는 FileNotFoundError를 발생시킵니다."""
        with pytest.raises(FileNotFoundError):
            load_graph("./nonexistent_path/graph.py:graph")
