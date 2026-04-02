"""백엔드: 로컬 파일시스템만 사용하는 가장 단순한 구성.

사용법:
    from agents.backends import create_filesystem_backend

    agent = create_deep_agent(backend=create_filesystem_backend())
"""

from __future__ import annotations

from deepagents.backends import FilesystemBackend

from agents.backends._defaults import ensure_output_dir, resolve_output_dir


def create_filesystem_backend(
    root_dir: str | None = None,
    virtual_mode: bool = True,
) -> FilesystemBackend:
    """로컬 파일시스템만 사용하는 가장 단순한 백엔드를 생성합니다.

    Args:
        root_dir: 루트 디렉토리 경로. None이면 AGENT_OUTPUT_DIR 또는 ./outputs 사용.
        virtual_mode: True면 root_dir 밖 접근 차단 (권장).

    지원 연산:
        - ls(path)              — 디렉토리 목록 조회
        - read_file(path)       — 파일 읽기
        - write_file(path, content) — 파일 생성·덮어쓰기
        - edit_file(path, edits)    — 파일 부분 수정
        - glob(pattern)         — 패턴으로 파일 검색 (예: "**/*.py")
        - grep(pattern, path)   — 파일 내용에서 텍스트 검색

    ※ 파일 업로드·다운로드는 지원하지 않습니다.
      원격 전송이 필요하면 커스텀 도구(@tool)를 추가하세요.

    적합한 경우:
        - 로컬 개발/테스트
        - 파일 읽기·쓰기만 필요한 단순 에이전트

    Returns:
        FilesystemBackend 인스턴스.
    """
    resolved = resolve_output_dir(root_dir)
    ensure_output_dir(resolved)
    return FilesystemBackend(root_dir=resolved, virtual_mode=virtual_mode)
