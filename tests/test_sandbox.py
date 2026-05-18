import pytest


@pytest.mark.asyncio
async def test_sandbox_exec():
    """Integration test requires Docker. Skip if not available."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    container_id = await mgr.start()
    assert container_id is not None

    result = await mgr.exec("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]

    await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_exec_failure():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    container_id = await mgr.start()
    result = await mgr.exec("exit 42")
    assert result["exit_code"] == 42
    await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_state():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    assert mgr.container_id is None

    await mgr.start()
    assert mgr.container_id is not None
    assert await mgr.is_running() is True

    await mgr.stop()
    assert await mgr.is_running() is False


@pytest.mark.asyncio
async def test_sandbox_install_tools():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    await mgr.start()
    await mgr.install_tools()
    result = await mgr.exec("which curl")
    assert result["exit_code"] == 0
    assert "curl" in result["stdout"]
    await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_exec_safe_timeout():
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager
    mgr = SandboxManager()
    await mgr.start()
    with pytest.raises(RuntimeError, match="timed out"):
        await mgr.exec_safe("sleep 30", timeout=2)
    await mgr.stop()
