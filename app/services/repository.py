"""Read-only repository access for ticket impact analysis."""

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class RepositorySnapshot:
    """Relevant read-only view of a repository branch."""

    repo_url: str
    branch: str
    local_path: Path
    candidate_files: list[str]
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
            candidate_files = self._candidate_files(
                repo_path,
                ticket_text,
                company.config_file_paths or [],
            )
        except Exception as exc:
            return RepositorySnapshot(
                repo_url=company.repo_url,
                branch=branch,
                local_path=repo_path,
                candidate_files=[],
                read_error=str(exc),
            )

        return RepositorySnapshot(
            repo_url=company.repo_url,
            branch=branch,
            local_path=repo_path,
            candidate_files=candidate_files,
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

    def _candidate_files(
        self,
        repo_path: Path,
        ticket_text: str,
        config_file_paths: list[str],
    ) -> list[str]:
        keywords = {
            word.lower()
            for word in ticket_text.replace("_", " ").replace("-", " ").split()
            if len(word) >= 4
        }
        configured_files = self._configured_files(repo_path, config_file_paths)
        scored_files: list[tuple[int, str]] = []

        for path in repo_path.rglob("*"):
            if not path.is_file() or self._is_ignored(path, repo_path) or not self._is_text_file(path):
                continue
            relative_path = path.relative_to(repo_path).as_posix()
            if relative_path in configured_files:
                continue
            score = self._score_file(path, relative_path, keywords)
            if score > 0 or path.suffix.lower() == ".py":
                scored_files.append((score, relative_path))

        scored_files.sort(key=lambda item: (-item[0], item[1]))
        return [*configured_files, *[relative_path for _, relative_path in scored_files]][:12]

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
