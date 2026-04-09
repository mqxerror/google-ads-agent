"""Settings API — manage MCP servers, credentials, and app configuration."""

from __future__ import annotations

import asyncio
import platform
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ── Models ──────────────────────────────────────────────────────

class MCPSettings(BaseModel):
    chrome_mcp_enabled: bool = False
    gtm_mcp_enabled: bool = False
    gtm_mcp_command: str = ""


class SettingsResponse(BaseModel):
    # MCP servers
    chrome_mcp_enabled: bool
    chrome_reuse_existing: bool
    chrome_use_default_profile: bool
    chrome_debug_port: int
    gtm_mcp_enabled: bool
    gtm_mcp_command: str
    # Google Ads (masked)
    google_ads_configured: bool
    google_ads_login_customer_id: str
    # MCP status
    mcp_status: dict


class SettingsUpdate(BaseModel):
    chrome_mcp_enabled: bool | None = None
    chrome_reuse_existing: bool | None = None
    chrome_use_default_profile: bool | None = None
    gtm_mcp_enabled: bool | None = None
    gtm_mcp_command: str | None = None


# ── Helpers ─────────────────────────────────────────────────────

async def _get_config(key: str, default: str = "") -> str:
    db = await get_db()
    try:
        cur = await db.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default
    finally:
        await db.close()


async def _set_config(key: str, value: str) -> None:
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO config (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            (key, value),
        )
        await db.commit()
    finally:
        await db.close()


async def load_settings_overrides() -> None:
    """Apply DB-stored config overrides to the runtime `settings` object.

    Called at backend startup (from main.py lifespan) and before each agent spawn
    (from agent.py) to ensure the Pydantic defaults from .env are overridden by
    user choices made via the Settings UI.
    """
    chrome_enabled = (await _get_config("chrome_mcp_enabled", str(settings.CHROME_MCP_ENABLED))).lower() == "true"
    chrome_reuse = (await _get_config("chrome_reuse_existing", str(settings.CHROME_REUSE_EXISTING))).lower() == "true"
    chrome_default_profile = (await _get_config("chrome_use_default_profile", str(settings.CHROME_USE_DEFAULT_PROFILE))).lower() == "true"
    gtm_enabled = (await _get_config("gtm_mcp_enabled", str(settings.GTM_MCP_ENABLED))).lower() == "true"
    gtm_command = await _get_config("gtm_mcp_command", settings.GTM_MCP_COMMAND)

    settings.CHROME_MCP_ENABLED = chrome_enabled
    settings.CHROME_REUSE_EXISTING = chrome_reuse
    settings.CHROME_USE_DEFAULT_PROFILE = chrome_default_profile
    settings.GTM_MCP_ENABLED = gtm_enabled
    if gtm_command:
        settings.GTM_MCP_COMMAND = gtm_command


def _find_chrome_binary() -> str | None:
    """Find the Chrome binary path on the current OS."""
    system = platform.system()
    candidates: list[str] = []
    if system == "Darwin":  # macOS
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        ]
    elif system == "Linux":
        candidates = [
            shutil.which("google-chrome") or "",
            shutil.which("google-chrome-stable") or "",
            shutil.which("chromium") or "",
            shutil.which("chromium-browser") or "",
        ]
    elif system == "Windows":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


async def _check_port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    """Check if a TCP port is open and accepting connections."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
        return False


async def _test_mcp_server(command: str, args: list[str], timeout: float = 45.0, extra_path: str = "") -> dict:
    """Actually start the MCP server and verify it speaks MCP protocol.

    Sends an MCP initialize message via stdio and waits for a valid response.
    Returns available=True only if the server responds correctly.
    Timeout is generous because `npx -y` may download packages on first run.
    """
    import os as _os
    if not command:
        return {"available": False, "reason": "not configured"}

    resolved = shutil.which(command) or command
    if not Path(resolved).exists() and not shutil.which(command):
        return {"available": False, "reason": f"command not found: {command}"}

    # MCP initialize request — minimal handshake
    init_request = (
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":'
        '{"protocolVersion":"2024-11-05","capabilities":{},'
        '"clientInfo":{"name":"status-check","version":"0.1.0"}}}\n'
    )

    env = dict(_os.environ)
    if extra_path:
        env["PATH"] = f"{extra_path}:{env.get('PATH', '')}"

    try:
        proc = await asyncio.create_subprocess_exec(
            resolved, *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            # Send initialize and read one line of response
            proc.stdin.write(init_request.encode())
            await proc.stdin.drain()

            line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)

            if line and b'"jsonrpc"' in line and b'"result"' in line:
                return {"available": True, "path": resolved}
            return {"available": False, "reason": "server did not respond with valid MCP handshake"}
        finally:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
    except asyncio.TimeoutError:
        return {"available": False, "reason": "server startup timed out (package install may be needed)"}
    except FileNotFoundError:
        return {"available": False, "reason": f"command not found: {command}"}
    except Exception as e:
        return {"available": False, "reason": f"failed to start: {e}"}


async def _get_mcp_status() -> dict:
    """Check status of all MCP servers by actually starting them."""
    status = {
        "google_ads": {
            "enabled": True,  # always enabled
            "available": True,
            "tools": "123 tools (core, targeting, bidding, planning, reporting)",
        },
    }

    # Check Chrome and GTM in parallel
    tasks = []

    chrome_enabled = settings.CHROME_MCP_ENABLED
    if chrome_enabled:
        if settings.CHROME_REUSE_EXISTING:
            # In reuse mode, check if Chrome is actually listening on the debug port
            port_available = await _check_port_open("127.0.0.1", settings.CHROME_DEBUG_PORT)
            if not port_available:
                status["chrome"] = {
                    "enabled": True,
                    "info": "Browser automation — GTM UI, landing pages, tag verification",
                    "available": False,
                    "reason": f"Chrome not running with --remote-debugging-port={settings.CHROME_DEBUG_PORT}. Quit Chrome and relaunch it with the debug port (see Settings below).",
                }
            else:
                status["chrome"] = {
                    "enabled": True,
                    "info": "Browser automation — connected to your existing Chrome (reuse mode)",
                    "available": True,
                }
        else:
            # Fresh browser mode — test the MCP server starts
            from app.services.agent import _MODERN_NPX
            chrome_cmd = _MODERN_NPX if settings.CHROME_MCP_COMMAND == "npx" else settings.CHROME_MCP_COMMAND
            extra_path = str(Path(chrome_cmd).parent) if chrome_cmd != "npx" else ""
            tasks.append(("chrome", _test_mcp_server(chrome_cmd, list(settings.CHROME_MCP_ARGS), extra_path=extra_path)))
    else:
        status["chrome"] = {"enabled": False, "info": "Browser automation for GTM, landing pages"}

    gtm_enabled = settings.GTM_MCP_ENABLED
    if gtm_enabled and settings.GTM_MCP_COMMAND:
        tasks.append(("gtm", _test_mcp_server(settings.GTM_MCP_COMMAND, [])))
    else:
        status["gtm"] = {
            "enabled": gtm_enabled,
            "available": False,
            "info": "Google Tag Manager API — programmatic tag management",
        }

    # Run all tests in parallel
    if tasks:
        results = await asyncio.gather(*[t[1] for t in tasks])
        for (name, _), result in zip(tasks, results):
            if name == "chrome":
                status["chrome"] = {
                    "enabled": True,
                    "info": "Browser automation — GTM UI, landing pages, tag verification",
                    **result,
                }
            elif name == "gtm":
                status["gtm"] = {
                    "enabled": True,
                    "tools": "50 tools (tags, triggers, variables, publishing)",
                    **result,
                }

    return status


# ── Endpoints ───────────────────────────────────────────────────

@router.get("")
async def get_settings() -> SettingsResponse:
    """Get current settings including MCP status."""
    # Apply DB overrides (these take priority over .env)
    await load_settings_overrides()

    return SettingsResponse(
        chrome_mcp_enabled=settings.CHROME_MCP_ENABLED,
        chrome_reuse_existing=settings.CHROME_REUSE_EXISTING,
        chrome_use_default_profile=settings.CHROME_USE_DEFAULT_PROFILE,
        chrome_debug_port=settings.CHROME_DEBUG_PORT,
        gtm_mcp_enabled=settings.GTM_MCP_ENABLED,
        gtm_mcp_command=settings.GTM_MCP_COMMAND,
        google_ads_configured=settings.has_google_ads_credentials,
        google_ads_login_customer_id=settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID or "",
        mcp_status=await _get_mcp_status(),
    )


@router.put("")
async def update_settings(body: SettingsUpdate):
    """Update settings. Changes take effect on next agent message."""
    if body.chrome_mcp_enabled is not None:
        await _set_config("chrome_mcp_enabled", str(body.chrome_mcp_enabled))
        settings.CHROME_MCP_ENABLED = body.chrome_mcp_enabled

    if body.chrome_reuse_existing is not None:
        await _set_config("chrome_reuse_existing", str(body.chrome_reuse_existing))
        settings.CHROME_REUSE_EXISTING = body.chrome_reuse_existing

    if body.chrome_use_default_profile is not None:
        await _set_config("chrome_use_default_profile", str(body.chrome_use_default_profile))
        settings.CHROME_USE_DEFAULT_PROFILE = body.chrome_use_default_profile

    if body.gtm_mcp_enabled is not None:
        await _set_config("gtm_mcp_enabled", str(body.gtm_mcp_enabled))
        settings.GTM_MCP_ENABLED = body.gtm_mcp_enabled

    if body.gtm_mcp_command is not None:
        await _set_config("gtm_mcp_command", body.gtm_mcp_command)
        settings.GTM_MCP_COMMAND = body.gtm_mcp_command

    # Regenerate MCP config for next agent session
    from app.services.agent import _get_mcp_config_path
    _get_mcp_config_path()

    return {"status": "ok", "mcp_status": await _get_mcp_status()}


# ── Chrome Launcher ─────────────────────────────────────────────

@router.post("/chrome/launch")
async def launch_chrome():
    """Launch Chrome with remote debugging enabled.

    Two modes controlled by CHROME_USE_DEFAULT_PROFILE:
    - True (default): Uses the user's own Chrome profile (all logins/tabs/extensions preserved).
      IMPORTANT: User must quit their existing Chrome first — Chrome only allows one instance
      per profile. The launched Chrome IS their regular Chrome, just with debugging enabled.
    - False: Uses a separate agent profile under the app's data directory. User needs to
      log in once but their main Chrome stays untouched.
    """
    # Check if already running on debug port
    if await _check_port_open("127.0.0.1", settings.CHROME_DEBUG_PORT):
        return {"status": "already_running", "message": f"Chrome is already listening on port {settings.CHROME_DEBUG_PORT}"}

    chrome_binary = _find_chrome_binary()
    if not chrome_binary:
        raise HTTPException(
            status_code=404,
            detail="Chrome not found. Install Google Chrome from https://www.google.com/chrome/",
        )

    # Always use a dedicated agent profile to avoid conflicts with the user's
    # main Chrome. The profile persists between launches so logins are remembered.
    # This lets users keep their main Chrome open while the agent works.
    profile_dir = settings.DATA_DIR / "chrome-agent-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        chrome_binary,
        f"--remote-debugging-port={settings.CHROME_DEBUG_PORT}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    use_default = False
    profile_msg = "Agent Chrome launched. Log in to Google/GTM once — logins are remembered between sessions. Your main Chrome stays untouched."

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to launch Chrome: {e}")

    # Wait up to 8 seconds for port to come up (first launch may be slow)
    for _ in range(16):
        await asyncio.sleep(0.5)
        if await _check_port_open("127.0.0.1", settings.CHROME_DEBUG_PORT):
            return {
                "status": "launched",
                "message": profile_msg,
                "use_default_profile": use_default,
            }

    raise HTTPException(
        status_code=500,
        detail="Chrome launched but isn't listening on the debug port. Another instance may be using port 9222.",
    )


@router.post("/chrome/stop")
async def stop_chrome():
    """Stop the agent's Chrome instance (kills processes using port 9222)."""
    if not await _check_port_open("127.0.0.1", settings.CHROME_DEBUG_PORT):
        return {"status": "not_running"}

    try:
        # Find and kill the Chrome process using the debug port
        result = subprocess.run(
            ["lsof", "-ti", f":{settings.CHROME_DEBUG_PORT}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        for pid in pids:
            try:
                subprocess.run(["kill", pid], timeout=3)
            except Exception:
                pass
        return {"status": "stopped", "killed_pids": pids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop Chrome: {e}")
