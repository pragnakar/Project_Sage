"""Sage Cloud entry point.

Usage:
  python -m sage_cloud                    # HTTP server + SSE transport (default)
  python -m sage_cloud --port 8001        # Custom port
  python -m sage_cloud --mcp-stdio        # MCP stdio transport only (for Claude Desktop)
  python -m sage_cloud --mcp-stdio --http # Both: stdio foreground, HTTP background
"""

import argparse
import asyncio
import importlib
import logging
import os
import secrets

logger = logging.getLogger(__name__)


def _generate_api_key() -> str:
    """Return the configured API key, or generate a fresh session key if none is set."""
    existing = os.environ.get("SAGE_CLOUD_API_KEYS", "").strip()
    if existing:
        return existing.split(",")[0]
    key = "sage_sk_" + secrets.token_hex(16)
    os.environ["SAGE_CLOUD_API_KEYS"] = key
    return key


async def _build_runtime():
    """Initialize ArtifactStore + ToolRegistry. Shared across transports."""
    from sage_cloud.artifact_store import ArtifactStore
    from sage_cloud.config import get_settings
    from sage_cloud.tools import ToolRegistry, register_core_tools

    settings = get_settings()
    store = ArtifactStore(
        db_path=settings.SAGE_CLOUD_DB_PATH,
        artifact_dir=settings.SAGE_CLOUD_ARTIFACT_DIR,
    )
    await store.init_db()

    registry = ToolRegistry()
    register_core_tools(registry, store)

    for app_name in settings.apps_list():
        try:
            module = importlib.import_module(f"sage_cloud_apps.{app_name}.loader")
            module.register(registry, store)
            logger.info("Loaded app module: %s", app_name)
        except ModuleNotFoundError:
            logger.warning("App module not found, skipping: %s", app_name)
        except Exception as e:
            logger.warning("Failed to load app module %s: %s", app_name, e)

    return store, registry


def _get_bound_port(server) -> int:
    """Extract the actual bound port from a uvicorn Server instance.

    When port=0 is used, the OS assigns a random port. This function
    retrieves the real port after the server has started.
    """
    for srv in server.servers:
        for sock in srv.sockets:
            addr = sock.getsockname()
            if isinstance(addr, tuple) and len(addr) >= 2:
                return addr[1]
    raise RuntimeError("Could not determine bound port from uvicorn server")


def main():
    parser = argparse.ArgumentParser(description="Sage Cloud")
    parser.add_argument("--mcp-stdio", action="store_true", help="Start MCP stdio transport")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Start HTTP server in background thread (only valid with --mcp-stdio)",
    )
    parser.add_argument("--port", type=int, default=None, help="HTTP server port (overrides settings)")
    args = parser.parse_args()

    api_key = _generate_api_key()

    if args.mcp_stdio:
        if args.http:
            import threading
            from sage_cloud.config import get_settings
            settings = get_settings()
            port = args.port if args.port is not None else settings.SAGE_CLOUD_PORT

            def _run_http():
                import uvicorn
                from sage_cloud.discovery import (
                    delete_discovery_file,
                    register_cleanup,
                    write_discovery_file,
                )
                # Route ALL uvicorn log output to stderr so stdout stays clean for
                # the MCP stdio JSON protocol. By default uvicorn's access log handler
                # writes to stdout, which corrupts the MCP message stream.
                log_config = uvicorn.config.LOGGING_CONFIG.copy()
                for handler in log_config.get("handlers", {}).values():
                    handler["stream"] = "ext://sys.stderr"

                config = uvicorn.Config(
                    "sage_cloud.server:app",
                    host=settings.SAGE_CLOUD_HOST,
                    port=port,
                    log_config=log_config,
                )
                server = uvicorn.Server(config)

                # Use a custom startup to capture the actual port
                original_startup = server.startup

                async def _patched_startup(sockets=None):
                    await original_startup(sockets=sockets)
                    try:
                        actual_port = _get_bound_port(server)
                        write_discovery_file(actual_port)
                        register_cleanup()
                        from sage_cloud.server import app as _app
                        _app.state.actual_port = actual_port
                    except Exception as exc:
                        logger.warning("Failed to write discovery file: %s", exc)

                server.startup = _patched_startup
                server.run()

            t = threading.Thread(target=_run_http, daemon=True)
            t.start()

        async def _run_stdio():
            from sage_cloud.mcp_transport import run_stdio
            store, registry = await _build_runtime()
            await run_stdio(store, registry)

        asyncio.run(_run_stdio())
    else:
        import uvicorn
        from sage_cloud.config import get_settings
        from sage_cloud.discovery import (
            delete_discovery_file,
            register_cleanup,
            write_discovery_file,
        )
        settings = get_settings()
        port = args.port if args.port is not None else settings.SAGE_CLOUD_PORT

        config = uvicorn.Config(
            "sage_cloud.server:app",
            host=settings.SAGE_CLOUD_HOST,
            port=port,
            reload=False,
        )
        server = uvicorn.Server(config)

        # Use a custom startup to capture the actual port and write discovery file
        original_startup = server.startup

        async def _patched_startup(sockets=None):
            await original_startup(sockets=sockets)
            try:
                actual_port = _get_bound_port(server)
                write_discovery_file(actual_port)
                register_cleanup()
                # Set actual_port on the app state so /api/config returns the right URL
                from sage_cloud.server import app as _app
                _app.state.actual_port = actual_port
                host_display = settings.SAGE_CLOUD_HOST if settings.SAGE_CLOUD_HOST != '0.0.0.0' else 'localhost'
                print(f"\n  Sage Cloud v0.3.0")
                print(f"  API Key : {api_key}")
                print(f"  Dashboard: http://{host_display}:{actual_port}/\n")
            except Exception as exc:
                logger.warning("Failed to write discovery file: %s", exc)
                print(f"\n  Sage Cloud v0.3.0")
                print(f"  API Key : {api_key}")
                host_display = settings.SAGE_CLOUD_HOST if settings.SAGE_CLOUD_HOST != '0.0.0.0' else 'localhost'
                print(f"  Dashboard: http://{host_display}:{port}/\n")

        server.startup = _patched_startup
        server.run()


if __name__ == "__main__":
    main()
