"""백엔드: 로컬 파일시스템 + 셸 명령 실행.

FilesystemBackend에 셸 실행 기능이 추가된 백엔드입니다.
코딩 에이전트처럼 파일 조작과 함께 명령어 실행이 필요할 때 사용합니다.

사용법:
    from agents.backends import create_local_shell_backend

    agent = create_deep_agent(backend=create_local_shell_backend())

⚠️ 주의: 셸 명령에 대한 제한이 없으므로, 신뢰할 수 있는 환경에서만 사용하세요.
"""

from __future__ import annotations

from deepagents.backends import LocalShellBackend

from agents.backends._defaults import resolve_output_dir


def create_local_shell_backend(
    root_dir: str | None = None,
    virtual_mode: bool = True,
) -> LocalShellBackend:
    """로컬 파일시스템 + 셸 실행 백엔드를 생성합니다.

    FilesystemBackend의 파일 읽기·쓰기 기능에 더해,
    셸 명령(pip install, git 등)을 직접 실행할 수 있습니다.

    Args:
        root_dir: 루트 디렉토리 경로. None이면 AGENT_OUTPUT_DIR 또는 ./outputs 사용.
        virtual_mode: True면 root_dir 밖 접근 차단 (권장).

    지원 연산 (FilesystemBackend 전체 + 셸):
        - ls(path)              — 디렉토리 목록 조회
        - read_file(path)       — 파일 읽기
        - write_file(path, content) — 파일 생성·덮어쓰기
        - edit_file(path, edits)    — 파일 부분 수정
        - glob(pattern)         — 패턴으로 파일 검색 (예: "**/*.py")
        - grep(pattern, path)   — 파일 내용에서 텍스트 검색
        - shell(command)        — 셸 명령 실행 (pip, git, pytest 등)

    ※ 파일 업로드·다운로드는 지원하지 않습니다.
      원격 전송이 필요하면 커스텀 도구(@tool)를 추가하세요.

    적합한 경우:
        - 코딩 에이전트 (파일 수정 + 테스트 실행)
        - 빌드·배포 자동화 에이전트
        - 로컬 환경에서 시스템 명령이 필요한 경우

    ⚠️ 주의:
        셸 명령에 대한 제한이 없으므로, 프로덕션 환경에서는
        샌드박스 백엔드(Modal, Daytona, Deno) 사용을 권장합니다.

    Returns:
        LocalShellBackend 인스턴스.
    """
    return LocalShellBackend(root_dir=resolve_output_dir(root_dir), virtual_mode=False)
