import asyncio
import shlex

import docker
from docker.errors import DockerException


class SandboxManager:
    LABEL_KEY = "brogrammer.build"
    LABEL_VALUE = "true"

    def __init__(self, image: str = "python:3.11-slim", workdir: str = "/workspace",
                 exec_timeout: int = 120):
        self.image = image
        self.workdir = workdir
        self.exec_timeout = exec_timeout
        self.container_id: str | None = None
        self._client: docker.DockerClient | None = None

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env(timeout=30)
        return self._client

    def _ensure_connected(self):
        client = self._get_client()
        client.ping()

    async def start(self) -> str:
        client = self._get_client()

        def _start():
            try:
                client.images.get(self.image)
            except docker.errors.ImageNotFound:
                client.images.pull(self.image)

            container = client.containers.run(
                self.image,
                command="tail -f /dev/null",
                detach=True,
                working_dir=self.workdir,
                stdin_open=True,
                tty=True,
                labels={self.LABEL_KEY: self.LABEL_VALUE},
            )
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

    async def exec(self, command: str) -> dict:
        if not self.container_id:
            raise RuntimeError("Sandbox not started")

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
                timeout=self.exec_timeout,
            )
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Sandbox command timed out after {self.exec_timeout}s: {command[:120]}"
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
        cmds = [
            "apt-get update -qq && apt-get install -y -qq curl nodejs npm 2>/dev/null",
            "pip install duckduckgo-search -q 2>/dev/null",
        ]
        for cmd in cmds:
            await self.exec(cmd)
        setattr(self, self.TOOLS_INSTALLED_ATTR, True)

    async def exec_safe(self, command: str, timeout: int = 15) -> dict:
        original_timeout = self.exec_timeout
        self.exec_timeout = timeout
        try:
            return await self.exec(command)
        finally:
            self.exec_timeout = original_timeout

    @staticmethod
    def build_tool_command(tool: str, args: list[str]) -> str:
        if tool == "curl":
            url = shlex.quote(args[0]) if args else ""
            return f"curl -sL --max-time 10 {url}"
        elif tool == "npm_view":
            pkg = shlex.quote(args[0]) if args else ""
            return f"npm view {pkg} --json 2>/dev/null"
        elif tool == "web_search":
            query = " ".join(shlex.quote(a) for a in args)
            return f'python3 -c "from duckduckgo_search import DDGS; print(list(DDGS().text({query}, max_results=5)))"'
        return ""
