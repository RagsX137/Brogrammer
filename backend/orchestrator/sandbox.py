import asyncio
import docker
from docker.errors import DockerException


class SandboxManager:
    def __init__(self, image: str = "python:3.11-slim", workdir: str = "/workspace"):
        self.image = image
        self.workdir = workdir
        self.container_id: str | None = None
        self._client = docker.from_env()

    async def start(self) -> str:
        def _create():
            container = self._client.containers.run(
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

        def _exec():
            container = self._client.containers.get(self.container_id)
            exit_code, output = container.exec_run(
                ["/bin/sh", "-c", command],
                demux=True,
            )
            if isinstance(output, tuple):
                stdout = output[0].decode("utf-8", errors="replace") if output[0] else ""
                stderr = output[1].decode("utf-8", errors="replace") if output[1] else ""
            else:
                stdout = str(output)
                stderr = ""
            return {"stdout": stdout, "stderr": stderr, "exit_code": exit_code}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _exec)

    async def is_running(self) -> bool:
        if not self.container_id:
            return False

        def _check():
            try:
                container = self._client.containers.get(self.container_id)
                return container.status == "running"
            except DockerException:
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    async def stop(self):
        if not self.container_id:
            return

        def _stop():
            try:
                container = self._client.containers.get(self.container_id)
                container.remove(force=True)
            except DockerException:
                pass
            self._client.close()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stop)
        self.container_id = None
