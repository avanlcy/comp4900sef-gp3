"""Runs Python inside a running Unreal Editor through Epic's remote-execution protocol.

Uses the reference client shipped with the engine (PythonScriptPlugin/Content/Python/
remote_execution.py), so it works even when no MCP server is attached. The editor must
have "Enable Remote Execution" on in Project Settings > Python (it is, in DefaultEngine.ini).

Usage (any system Python 3):
    python tools/ue_remote.py --file comp4900sef/Script/df_resave_test_track.py
    python tools/ue_remote.py --code "import unreal; print(unreal.EditorLevelLibrary.get_editor_world().get_name())"
    python tools/ue_remote.py --console "Automation RunTests DeadFire.PIE"
"""
import argparse
import json
import os
import sys
import time

ENGINE = os.environ.get("UE_ENGINE_PATH", r"D:\UE_4.27")
CLIENT_DIR = os.path.join(ENGINE, "Engine", "Plugins", "Experimental", "PythonScriptPlugin", "Content", "Python")
sys.path.insert(0, CLIENT_DIR)

# The 4.27 client calls json.loads(..., encoding=...), an argument Python 3.9 removed.
_original_loads = json.loads


def _loads_compat(payload, *args, **kwargs):
    kwargs.pop("encoding", None)
    return _original_loads(payload, *args, **kwargs)


json.loads = _loads_compat

import remote_execution as remote  # noqa: E402


def connect(timeout_seconds=15.0):
    config = remote.RemoteExecutionConfig()
    # Must match RemoteExecutionMulticastBindAddress in Config/DefaultEngine.ini (loopback, so VPN
    # or network-adapter changes cannot break the link). Override with UE_REMOTE_BIND if needed.
    config.multicast_bind_address = os.environ.get("UE_REMOTE_BIND", "127.0.0.1")
    session = remote.RemoteExecution(config)
    session.start()
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        nodes = session.remote_nodes
        if nodes:
            session.open_command_connection(nodes[0]["node_id"])
            return session
        time.sleep(0.5)
    session.stop()
    raise SystemExit("no Unreal Editor with remote execution found within {:.0f}s".format(timeout_seconds))


def run(session, code, exec_type="ExecuteFile"):
    result = session.run_command(code, exec_mode=exec_type)
    for line in result.get("output", []):
        print("[{}] {}".format(line.get("type", "Info"), line.get("output", "")))
    if not result.get("success", False):
        print("FAILED: {}".format(result.get("result", "")))
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Python file to execute inside the editor")
    group.add_argument("--code", help="Python statements to execute inside the editor")
    group.add_argument("--console", help="Editor console command to run (e.g. 'Automation RunTests DeadFire')")
    args = parser.parse_args()

    session = connect()
    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as handle:
                ok = run(session, handle.read(), "ExecuteFile")
        elif args.code:
            ok = run(session, args.code, "ExecuteFile")
        else:
            code = (
                "import unreal\n"
                "unreal.SystemLibrary.execute_console_command(unreal.EditorLevelLibrary.get_editor_world(), {!r})\n"
                "print('console command sent')\n"
            ).format(args.console)
            ok = run(session, code, "ExecuteFile")
    finally:
        session.close_command_connection()
        session.stop()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
