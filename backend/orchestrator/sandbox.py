import asyncio
import ipaddress
import os
import re
import shlex
from pathlib import Path
from urllib.parse import urlparse

import docker
from docker.errors import DockerException

from backend.core import config


class SandboxManager:
    LABEL_KEY = "brogrammer.build"
    LABEL_VALUE = "true"

    def __init__(self, image: str | None = None, workdir: str | None = None,
                 exec_timeout: int | None = None):
        self.image = image or config.get("SANDBOX_IMAGE", "brogrammer/sandbox:latest")
        self.workdir = workdir or config.get("SANDBOX_WORKDIR", "/workspace")
        self.exec_timeout = exec_timeout if exec_timeout is not None else config.get_int("SANDBOX_EXEC_TIMEOUT", 120)
        self.container_id: str | None = None
        self.host_workdir: str | None = None
        self._client: docker.DockerClient | None = None

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env(timeout=30)
        return self._client

    def _ensure_connected(self):
        client = self._get_client()
        client.ping()

    PREBUILT_IMAGE = "brogrammer/sandbox:latest"
    FALLBACK_IMAGE = "python:3.11-slim"

    async def start(self, host_workdir: str | None = None) -> str:
        client = self._get_client()
        self.host_workdir = host_workdir

        if self.host_workdir:
            Path(self.host_workdir).mkdir(parents=True, exist_ok=True)

        def _resolve_image():
            try:
                client.images.get(self.image)
                return self.image
            except docker.errors.ImageNotFound:
                if self.image == self.PREBUILT_IMAGE:
                    print(f"Image {self.PREBUILT_IMAGE} not found, falling back to {self.FALLBACK_IMAGE}")
                    return self.FALLBACK_IMAGE
                client.images.pull(self.image)
                return self.image

        def _start():
            resolved = _resolve_image()
            kwargs = dict(
                image=resolved,
                command="tail -f /dev/null",
                detach=True,
                working_dir=self.workdir,
                stdin_open=True,
                tty=True,
                labels={self.LABEL_KEY: self.LABEL_VALUE},
            )
            if self.host_workdir:
                kwargs["volumes"] = {self.host_workdir: {"bind": self.workdir, "mode": "rw"}}

            container = client.containers.run(**kwargs)
            return container.id

        loop = asyncio.get_event_loop()
        try:
            self.container_id = await asyncio.wait_for(
                loop.run_in_executor(None, _start),
                timeout=180,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Docker sandbox failed to start within 180s — "
                f"try 'docker pull {self.image}' manually"
            )
        return self.container_id

    async def exec(self, command: str, timeout: int | None = None) -> dict:
        if not self.container_id:
            raise RuntimeError("Sandbox not started")

        effective_timeout = timeout if timeout is not None else self.exec_timeout
        client = self._get_client()

        def _exec():
            container = client.containers.get(self.container_id)
            exit_code, raw_output = container.exec_run(
                ["/bin/sh", "-c", command],
                demux=True,
            )
            if isinstance(raw_output, tuple):
                stdout = raw_output[0].decode("utf-8", errors="replace") if raw_output[0] else ""
                stderr = raw_output[1].decode("utf-8", errors="replace") if raw_output[1] else ""
            else:
                stdout = raw_output.decode("utf-8", errors="replace")
                stderr = ""
            return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}

        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, _exec),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Sandbox command timed out after {effective_timeout}s: {command[:120]}"
            )

    async def is_running(self) -> bool:
        if not self.container_id:
            return False

        client = self._get_client()

        def _check():
            try:
                container = client.containers.get(self.container_id)
                return container.status == "running"
            except DockerException:
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    async def stop(self):
        if not self.container_id:
            return

        client = self._get_client()

        def _stop():
            try:
                container = client.containers.get(self.container_id)
                container.remove(force=True)
            except DockerException:
                pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stop)
        self.container_id = None

    @classmethod
    def cleanup_orphans(cls):
        try:
            client = docker.from_env(timeout=10)
            orphans = client.containers.list(
                all=True,
                filters={"label": f"{cls.LABEL_KEY}={cls.LABEL_VALUE}"},
            )
            for c in orphans:
                try:
                    c.remove(force=True)
                except DockerException:
                    pass
        except DockerException:
            pass

    TOOLS_INSTALLED_ATTR = "_tools_installed"

    async def install_tools(self) -> None:
        if getattr(self, self.TOOLS_INSTALLED_ATTR, False):
            return
        if self.container_id and self.image == self.PREBUILT_IMAGE:
            setattr(self, self.TOOLS_INSTALLED_ATTR, True)
            return
        cmds = [
            "apt-get update -qq && apt-get install -y -qq curl nodejs npm 2>/dev/null",
            "pip install duckduckgo-search -q 2>/dev/null",
        ]
        for cmd in cmds:
            result = await self.exec(cmd, timeout=120)
            if result.get("exit_code", -1) != 0:
                stderr = result.get("stderr", "")
                raise RuntimeError(f"install_tools failed: {stderr[:500]}" if stderr else f"install_tools failed for: {cmd[:80]}")

        probes = [
            ("curl", "which curl"),
            ("npm", "which npm"),
            ("duckduckgo_search", 'python3 -c "import duckduckgo_search" 2>&1'),
        ]
        for name, probe_cmd in probes:
            probe_result = await self.exec(probe_cmd)
            if probe_result.get("exit_code", -1) != 0:
                raise RuntimeError(
                    f"install_tools: {name} not found after install — "
                    f"stderr: {probe_result.get('stderr', '')[:200]}"
                )
        setattr(self, self.TOOLS_INSTALLED_ATTR, True)

    async def exec_safe(self, command: str, timeout: int = 15) -> dict:
        return await self.exec(command, timeout=timeout)

    @staticmethod
    def validate_url(url_str: str) -> str:
        parsed = urlparse(url_str)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"URL scheme '{parsed.scheme}' not allowed — only http and https")
        host = parsed.hostname or ""
        deny_patterns = [
            r"^localhost$",
            r"^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
            r"^169\.254\.\d{1,3}\.\d{1,3}$",
            r"^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$",
            r"^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$",
            r"^192\.168\.\d{1,3}\.\d{1,3}$",
            r"^\[::1\]$",
            r"^\[fe80::",  # IPv6 link-local
            r"metadata\.google\.internal$",
        ]
        for pat in deny_patterns:
            if re.match(pat, host, re.IGNORECASE):
                raise ValueError(f"URL host '{host}' is in the denylist")
        allowlist = os.environ.get("SKEPTIC_CURL_ALLOWLIST", "")
        if allowlist:
            allowed_suffixes = [s.strip() for s in allowlist.split(",")]
            if not any(host.endswith(suffix) for suffix in allowed_suffixes):
                raise ValueError(f"URL host '{host}' not in SKEPTIC_CURL_ALLOWLIST")
        return url_str

    @staticmethod
    def build_tool_command(tool: str, args: list[str]) -> str:
        if tool == "curl":
            url = args[0] if args else ""
            if not url:
                return ""
            SandboxManager.validate_url(url)
            safe_url = shlex.quote(url)
            return f"curl -sL --max-time 10 {safe_url}"
        elif tool == "npm_view":
            pkg = shlex.quote(args[0]) if args else ""
            return f"npm view {pkg} --json 2>/dev/null"
        elif tool == "web_search":
            query = " ".join(shlex.quote(a) for a in args)
            return f'python3 -c "from duckduckgo_search import DDGS; print(list(DDGS().text({query}, max_results=5)))"'
        return ""
