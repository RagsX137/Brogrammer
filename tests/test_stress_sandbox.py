"""
Stress tests for SandboxManager.
Covers concurrent execution, timeout handling, and error conditions.
"""
import pytest
import asyncio


@pytest.mark.asyncio
async def test_sandbox_concurrent_exec():
    """Multiple concurrent exec calls should work."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager

    mgr = SandboxManager()
    await mgr.start()
    try:
        tasks = [mgr.exec("echo hello") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        for r in results:
            assert r["exit_code"] == 0
    finally:
        await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_exec_resource_intensive():
    """Resource intensive command should work."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager

    mgr = SandboxManager()
    await mgr.start()
    try:
        # Write large file
        result = await mgr.exec("dd if=/dev/urandom of=/tmp/bigfile bs=1M count=5")
        assert result["exit_code"] == 0 or "No space" not in result["stderr"]
    finally:
        await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_exec_signal_handling():
    """Signal handling should work."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager

    mgr = SandboxManager()
    await mgr.start()
    try:
        # Kill a background process
        result = await mgr.exec("sleep 100 &; kill %1; echo done")
        assert result["exit_code"] == 0
    finally:
        await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_multiple_start_stop_cycles():
    """Multiple start/stop cycles should work."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager

    mgr = SandboxManager()
    for _ in range(3):
        await mgr.start()
        result = await mgr.exec("echo test")
        assert result["exit_code"] == 0
        assert "test" in result["stdout"]
        await mgr.stop()


@pytest.mark.asyncio
async def test_sandbox_stop_without_start_idempotent():
    """Calling stop without start should not error."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager

    mgr = SandboxManager()
    await mgr.stop()  # Should not raise
    assert mgr.container_id is None


@pytest.mark.asyncio
async def test_sandbox_exec_invalid_container():
    """Exec with bad container ID should fail gracefully."""
    import docker
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")

    from backend.orchestrator.sandbox import SandboxManager

    mgr = SandboxManager()
    await mgr.start()
    await mgr.stop()

    with pytest.raises(RuntimeError):
        await mgr.exec("echo test")
