"""Read-only repository access for ticket impact analysis."""

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.db.models.company import Company

TEXT_EXTENSIONS = {
    ".cfg",
    ".css",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sql",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_FILE_NAMES = {".env", ".env.example", "Dockerfile"}
IGNORED_DIRS = {".git", ".venv", "__pycache__", "node_modules", "dist", "build", ".pytest_cache", ".ruff_cache"}
INDEX_FILE_NAME = ".ai_smartec_index.json"


@dataclass(frozen=True)
class RepositorySnapshot:
    """Relevant read-only view of a repository branch."""

    repo_url: str
    branch: str
    local_path: Path
    candidate_files: list[str]
    all_files: list[str] = field(default_factory=list)
    text_files: list[str] = field(default_factory=list)
    resource_files: list[str] = field(default_factory=list)
    commit_hash: str | None = None
    read_error: str | None = None


class RepositoryReader:
    """Clone or update configured repositories and inspect candidate files."""

    def __init__(self, cache_dir: str = settings.repository_cache_dir) -> None:
        self.cache_dir = Path(cache_dir)

    async def snapshot_for_company(self, company: Company | None, ticket_text: str) -> RepositorySnapshot | None:
        """Return a repository snapshot for a company when repo settings exist."""
        if company is None or not company.repo_url:
            return None

        branch = company.repo_branch or "master"
        repo_path = self._repo_path(company.repo_url, branch)
        try:
            await self._ensure_checkout(company.repo_url, branch, repo_path)
            commit_hash = await self._current_commit(repo_path)
            repo_index = self._repo_index(repo_path, commit_hash)
            candidate_files = self._candidate_files(
                repo_path,
                ticket_text,
                company.config_file_paths or [],
                repo_index,
            )
        except Exception as exc:
            return RepositorySnapshot(
                repo_url=company.repo_url,
                branch=branch,
                local_path=repo_path,
                candidate_files=[],
                all_files=[],
                text_files=[],
                resource_files=[],
                commit_hash=None,
                read_error=str(exc),
            )

        return RepositorySnapshot(
            repo_url=company.repo_url,
            branch=branch,
            local_path=repo_path,
            candidate_files=candidate_files,
            all_files=repo_index["all_files"],
            text_files=repo_index["text_files"],
            resource_files=repo_index["resource_files"],
            commit_hash=commit_hash,
        )

    def _repo_path(self, repo_url: str, branch: str) -> Path:
        repo_key = hashlib.sha256(f"{repo_url}@{branch}".encode()).hexdigest()[:16]
        return self.cache_dir / repo_key

    async def _ensure_checkout(self, repo_url: str, branch: str, repo_path: Path) -> None:
        await asyncio.to_thread(self.cache_dir.mkdir, parents=True, exist_ok=True)
        repo_exists = await asyncio.to_thread(repo_path.exists)
        if not repo_exists:
            await self._run_git("clone", "--depth", "1", "--branch", branch, repo_url, str(repo_path))
            return

        await self._run_git("-C", str(repo_path), "fetch", "origin", branch, "--depth", "1")
        await self._run_git("-C", str(repo_path), "checkout", branch)
        await self._run_git("-C", str(repo_path), "reset", "--hard", f"origin/{branch}")

    async def _run_git(self, *args: str) -> None:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45)
        except TimeoutError as exc:
            process.kill()
            raise RuntimeError("Git operation timed out") from exc

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="ignore") or stdout.decode("utf-8", errors="ignore")
            raise RuntimeError(detail.strip() or "Git operation failed")

    async def _current_commit(self, repo_path: Path) -> str:
        return await self._run_git_stdout("-C", str(repo_path), "rev-parse", "HEAD")

    async def _run_git_stdout(self, *args: str) -> str:
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=45)
        except TimeoutError as exc:
            process.kill()
            raise RuntimeError("Git operation timed out") from exc

        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="ignore") or stdout.decode("utf-8", errors="ignore")
            raise RuntimeError(detail.strip() or "Git operation failed")
        return stdout.decode("utf-8", errors="ignore").strip()

    def _repo_index(self, repo_path: Path, commit_hash: str) -> dict[str, Any]:
        index_path = repo_path / INDEX_FILE_NAME
        try:
            cached = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = {}
        if cached.get("commit_hash") == commit_hash:
            return cached

        all_files = self._repo_files(repo_path)
        text_files = [file_path for file_path in all_files if self._is_text_file(repo_path / file_path)]
        resource_files = [file_path for file_path in all_files if file_path not in text_files]
        repo_index = {
            "commit_hash": commit_hash,
            "all_files": all_files,
            "text_files": text_files,
            "resource_files": resource_files,
        }
        try:
            index_path.write_text(json.dumps(repo_index, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass
        return repo_index

    def _candidate_files(
        self,
        repo_path: Path,
        ticket_text: str,
        config_file_paths: list[str],
        repo_index: dict[str, Any] | None = None,
    ) -> list[str]:
        keywords = {
            word.lower()
            for word in ticket_text.replace("_", " ").replace("-", " ").split()
            if len(word) >= 4
        }
        configured_files = self._configured_files(repo_path, config_file_paths)
        scored_files: list[tuple[int, int, str]] = []

        text_files = (
            repo_index["text_files"]
            if repo_index
            else [file_path for file_path in self._repo_files(repo_path) if self._is_text_file(repo_path / file_path)]
        )
        for relative_path in text_files:
            if relative_path in configured_files:
                continue
            path = repo_path / relative_path
            score = self._score_file(path, relative_path, keywords)
            file_type_priority = 0 if score > 0 else 1 if path.suffix.lower() == ".py" else 2
            scored_files.append((file_type_priority, -score, relative_path))

        scored_files.sort()
        return [*configured_files, *[relative_path for _, _, relative_path in scored_files]]

    def _configured_files(self, repo_path: Path, config_file_paths: list[str]) -> list[str]:
        configured_files: list[str] = []
        for configured_path in config_file_paths:
            if not configured_path:
                continue
            file_path = (repo_path / configured_path).resolve()
            try:
                file_path.relative_to(repo_path.resolve())
            except ValueError:
                continue
            if (
                file_path.is_file()
                and not self._is_ignored(file_path, repo_path)
                and self._is_text_file(file_path)
            ):
                configured_files.append(file_path.relative_to(repo_path).as_posix())
        return list(dict.fromkeys(configured_files))

    def _repo_files(self, repo_path: Path) -> list[str]:
        files: list[str] = []
        for path in repo_path.rglob("*"):
            if path.is_file() and path.name != INDEX_FILE_NAME and not self._is_ignored(path, repo_path):
                files.append(path.relative_to(repo_path).as_posix())
        return sorted(files)

    def _is_text_file(self, path: Path) -> bool:
        return path.name in TEXT_FILE_NAMES or path.suffix.lower() in TEXT_EXTENSIONS

    def _is_ignored(self, path: Path, repo_path: Path) -> bool:
        relative_parts = path.relative_to(repo_path).parts
        return any(part in IGNORED_DIRS for part in relative_parts)

    def _score_file(self, path: Path, relative_path: str, keywords: set[str]) -> int:
        score = sum(2 for keyword in keywords if keyword in relative_path.lower())
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")[:25_000].lower()
        except OSError:
            return score
        score += sum(1 for keyword in keywords if keyword in content)
        return score
