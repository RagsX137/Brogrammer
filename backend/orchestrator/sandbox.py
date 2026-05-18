import asyncio
import docker
from docker.errors import DockerException


class SandboxManager:
    def __init__(self, image: str = "python:3.11-slim", workdir: str = "/workspace"):
        self.image = image
        self.workdir = workdir
        self.container_id: str | None = None
        self._client: docker.DockerClient | None = None

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    async def start(self) -> str:
        client = self._get_client()

        def _create():
            container = client.containers.run(
                self.image,
                command="tail -f /dev/null",
                detach=True,
                working_dir=self.workdir,
                stdin_open=True,
                tty=True,
            )
            return container.id

        loop = asyncio.get_event_loop()
        self.container_id = await loop.run_in_executor(None, _create)
        return self.container_id

    async def exec(self, command: str) -> dict:
        if not self.container_id:
            raise RuntimeError("Sandbox not started")

        client = self._get_client()

        def _exec():
            container = client.containers.get(self.container_id)
            exit_code, output = container.exec_run(
                ["/bin/sh", "-c", command],
                demux=True,
            )
            stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
            stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
            return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _exec)

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
            client.close()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stop)
        self.container_id = None
