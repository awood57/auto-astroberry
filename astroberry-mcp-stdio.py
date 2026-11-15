#!/usr/bin/env python3
"""Private stdio transport for KStars' native MCP endpoint.

Runs on the Pi through SSH. Credentials stay in the desktop keyring.
Defaults to read-only. --control enables the configured observing tools.
Starting this transport never starts KStars or operates equipment.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ENDPOINT = "http://127.0.0.1:8765/mcp"
READ_TOOLS = frozenset({
    "ekos_status", "catalog_search", "mount_coords", "mount_get_slew_rates",
    "focuser_status", "image_last_info", "image_last_thumbnail", "align_status",
    "align_get_solver_action", "align_get_target_coords", "align_result",
    "scheduler_status", "scheduler_jobs", "scheduler_current_job",
    "capture_status", "capture_get_jobs", "focus_status", "focus_hfr_samples",
})
CONTROL_TOOLS = frozenset({
    "mount_goto", "mount_goto_target", "mount_abort", "mount_set_tracking",
    "mount_set_track_mode", "scheduler_load", "scheduler_start", "scheduler_stop",
    "capture_load_sequence", "capture_set_target", "capture_start", "capture_stop",
    "capture_abort", "capture_suspend", "capture_pause", "capture_resume",
    "align_solve", "align_set_solver_action", "align_set_solver_mode",
    "align_set_target_coords", "align_abort",
})
POLICY_PATH = Path(__file__).with_name("observatory.local.json")


def load_setup():
    setup = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    for field in ("plan_directory", "capture_directory"):
        directory = Path(setup[field]).expanduser()
        if not directory.is_absolute():
            raise ValueError(f"{field} must start with ~ or be absolute.")
        setup[field] = str(directory.resolve())
    if not isinstance(setup["profile"], str) or not setup["profile"].strip():
        raise ValueError("Set the local Ekos profile name.")
    return setup


SETUP_TOOL = {
    "name": "observatory_setup",
    "description": "Read the configured equipment, observing workflow, and outstanding live checks. Read this before planning an observing run.",
    "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    "annotations": {"readOnlyHint": True, "destructiveHint": False,
                    "idempotentHint": True, "openWorldHint": False},
}


def validate_plan_file(name, arguments, setup):
    """Limit loadable files; never execute or load them during validation."""
    raw_path = arguments.get("path")
    if not isinstance(raw_path, str):
        raise ValueError("An absolute plan-file path is required.")
    path = Path(raw_path)
    if not path.is_absolute():
        raise ValueError("An absolute plan-file path is required.")
    path = path.resolve(strict=True)
    if not path.is_relative_to(Path(setup["plan_directory"])):
        raise ValueError("Plan files must remain inside the configured plan directory.")
    expected = "SchedulerList" if name == "scheduler_load" else "SequenceQueue"
    suffix = ".esl" if name == "scheduler_load" else ".esq"
    if path.suffix.lower() != suffix or path.stat().st_size > 1_000_000:
        raise ValueError("Invalid plan file type or size.")
    content = path.read_bytes()
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("External XML declarations are not supported.")
    root = ET.fromstring(content)
    if root.tag != expected:
        raise ValueError("Incorrect KStars plan-file root.")
    for item in root.iter():
        if "script" in item.tag.lower() and ((item.text or "").strip() or len(item) or item.attrib):
            raise ValueError("Automatic scripts are not enabled for this setup.")
        if item.tag == "Procedure" and (item.text or "").strip():
            raise ValueError("Automatic startup/parking/shutdown procedures need live validation first.")
        if item.tag == "Step" and (item.text or "").strip() not in {"Track", "Align"}:
            raise ValueError("Automatic guiding and focusing are not configured.")
    if name == "scheduler_load":
        if root.findtext("Profile") != setup["profile"]:
            raise ValueError("Scheduler plans must use the configured equipment profile.")
        for sequence in root.iter("Sequence"):
            validate_plan_file("capture_load_sequence", {"path": (sequence.text or "").strip()}, setup)
    return str(path)


def desktop_environment():
    env = os.environ.copy()
    if env.get("DBUS_SESSION_BUS_ADDRESS"):
        return env
    bus = Path("/run/user") / str(os.getuid()) / "bus"
    if bus.is_socket():
        env["DBUS_SESSION_BUS_ADDRESS"] = "unix:path=" + str(bus)
        return env
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            if proc.stat().st_uid != os.getuid():
                continue
            if (proc / "comm").read_text().strip() != "xfce4-session":
                continue
            for entry in (proc / "environ").read_bytes().split(b"\0"):
                name, _, value = entry.partition(b"=")
                if name in (b"DBUS_SESSION_BUS_ADDRESS", b"DISPLAY", b"XAUTHORITY"):
                    env[name.decode()] = value.decode()
            return env
        except (PermissionError, FileNotFoundError, ProcessLookupError):
            continue
    raise RuntimeError("Open the Astroberry desktop and KStars MCP first.")


def read_token(control=False):
    result = subprocess.run(
        ["secret-tool", "lookup", "user", "mcp_token" if control else "mcp_readonly_token", "server", "kstars",
         "type", "plaintext"],
        env=desktop_environment(), capture_output=True, text=True, timeout=20,
    )
    token = result.stdout.strip()
    if result.returncode or not token:
        raise RuntimeError("Unlock the Astroberry desktop keyring; the MCP token is unavailable.")
    return token


def error(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


def upstream(message, token):
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(message).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Authorization": "Bearer " + token},
    )
    # Never inherit proxy settings or forward credentials across a redirect.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    with opener.open(request, timeout=20) as response:
        return json.load(response)


def handle(message, token, control=False):
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return error(None, -32600, "Invalid JSON-RPC request")
    # KStars' HTTP endpoint is request/response; no subscription is needed here.
    if "id" not in message:
        return None
    request_id = message["id"]
    method = message.get("method")
    params = message.get("params", {})
    if not isinstance(params, dict):
        return error(request_id, -32602, "Parameters must be an object")
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method not in ("initialize", "tools/list", "tools/call"):
        return error(request_id, -32601, "Unsupported method")
    if method == "tools/call":
        name = params.get("name")
        if name == "observatory_setup":
            policy = load_setup()
            policy["connection_mode"] = "control" if control else "read-only"
            return {"jsonrpc": "2.0", "id": request_id, "result": {
                "content": [{"type": "text", "text": json.dumps(policy)}]}}
        allowed = READ_TOOLS | CONTROL_TOOLS if control else READ_TOOLS
        if not isinstance(name, str) or name not in allowed:
            return error(request_id, -32602, "This tool is not enabled for this connection.")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return error(request_id, -32602, "Tool arguments must be an object.")
        if name in {"scheduler_load", "capture_load_sequence"}:
            try:
                validate_plan_file(name, arguments, load_setup())
            except (ValueError, OSError, ET.ParseError) as exc:
                return error(request_id, -32602, str(exc))
        if name == "mount_set_track_mode" and arguments.get("mode") != "sidereal":
            return error(request_id, -32602, "Only sidereal tracking is enabled for this night-sky setup.")
    response = upstream(message, token)
    if method == "tools/list" and isinstance(response.get("result"), dict):
        response["result"]["tools"] = [
            tool for tool in response["result"].get("tools", [])
            if (tool.get("name") in READ_TOOLS
                and tool.get("annotations", {}).get("readOnlyHint") is True)
            or (control and tool.get("name") in CONTROL_TOOLS)
        ]
        response["result"]["tools"].append(SETUP_TOOL)
    if method == "initialize" and isinstance(response.get("result"), dict):
        response["result"]["instructions"] = (
            "Before any operation, read observatory_setup. Never move equipment or take "
            "exposures merely to test setup. Before an observing run, obtain the user's "
            "approval of the target, framing, exposure/count, end time and finish behaviour. "
            "Confirm hardware readiness, site/time, hand-controller alignment, manual focus, "
            "sky conditions and clearance. Inspect a short approved test exposure for real "
            "stars and target framing before starting a long sequence. "
            + ("Control is enabled for the listed tools. " if control else
               "This connection is read-only and cannot operate hardware. ")
            + "Use the configured profile, train and directories from observatory_setup. "
            "Keep the run supervised and preserve active queues. "
            "A keyring unlock is authentication, not approval of an observing plan. "
            "Monitor the run and report saved frame counts, actual integration, quality and "
            "paths. Keep this chat active during runs; unattended failure/shutdown behaviour "
            "is not yet commissioned. Do not claim a successful capture without saved files."
        )
    return response


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", action="store_true")
    args = parser.parse_args()
    try:
        load_setup()
        token = read_token(args.control)
    except (KeyError, TypeError, ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for line in sys.stdin:
        request_id = None
        try:
            message = json.loads(line)
            if isinstance(message, dict):
                request_id = message.get("id")
            response = handle(message, token, args.control)
        except json.JSONDecodeError:
            response = error(None, -32700, "Invalid JSON")
        except urllib.error.HTTPError as exc:
            response = error(request_id, -32000,
                             f"KStars returned HTTP {exc.code}; check MCP and keyring authentication.")
        except (urllib.error.URLError, TimeoutError, OSError):
            response = error(request_id, -32000,
                             "KStars MCP is unavailable; open KStars MCP on the Pi and unlock its keyring.")
        if response is not None:
            print(json.dumps(response, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
