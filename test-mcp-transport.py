"""Offline checks: no network access, credentials, or equipment commands."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile

spec = importlib.util.spec_from_file_location(
    "bridge", Path(__file__).with_name("astroberry-mcp-stdio.py")
)
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


class ReadOnlyTransportTests(unittest.TestCase):
    def test_writable_and_unknown_tools_never_reach_kstars(self):
        with patch.object(bridge, "upstream") as upstream:
            for name in ("mount_goto", "capture_start", "scheduler_start", "new_tool", []):
                message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": name, "arguments": {}}}
                self.assertEqual(bridge.handle(message, "test")["error"]["code"], -32602)
            upstream.assert_not_called()

    def test_discovery_requires_allowlist_and_read_only_annotation(self):
        data = {"jsonrpc": "2.0", "id": 1, "result": {"tools": [
            {"name": "ekos_status", "annotations": {"readOnlyHint": True}},
            {"name": "capture_start", "annotations": {"readOnlyHint": True}},
            {"name": "mount_coords", "annotations": {"readOnlyHint": False}},
        ]}}
        with patch.object(bridge, "upstream", return_value=data):
            result = bridge.handle({"jsonrpc": "2.0", "id": 1,
                                    "method": "tools/list"}, "test")
        self.assertEqual([t["name"] for t in result["result"]["tools"]], ["ekos_status", "observatory_setup"])

    def test_status_is_forwarded(self):
        message = {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                   "params": {"name": "ekos_status", "arguments": {}}}
        expected = {"jsonrpc": "2.0", "id": 7, "result": {"content": []}}
        with patch.object(bridge, "upstream", return_value=expected) as upstream:
            self.assertEqual(bridge.handle(message, "test"), expected)
            upstream.assert_called_once_with(message, "test")

    def test_notifications_and_unsupported_methods_are_not_forwarded(self):
        with patch.object(bridge, "upstream") as upstream:
            self.assertIsNone(bridge.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}, "test"))
            result = bridge.handle({"jsonrpc": "2.0", "id": 1,
                                    "method": "resources/read"}, "test")
            self.assertEqual(result["error"]["code"], -32601)
            upstream.assert_not_called()

    def test_control_is_opt_in_and_sensitive_tools_stay_unavailable(self):
        with patch.object(bridge, "upstream", return_value={"result": {}}) as upstream:
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "capture_start", "arguments": {}}}
            self.assertIn("error", bridge.handle(request, "test"))
            upstream.assert_not_called()
            self.assertIn("result", bridge.handle(request, "test", control=True))
            upstream.assert_called_once()
            upstream.reset_mock()
            for name in ("mount_sync", "mount_park", "mount_unpark", "focus_auto", "mount_set_meridian_flip"):
                request["params"]["name"] = name
                self.assertIn("error", bridge.handle(request, "test", control=True))
            upstream.assert_not_called()

    def test_plan_paths_and_embedded_automation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "plans"
            root.mkdir()
            setup = {"plan_directory": str(root), "profile": "Portable Rig"}
            good = root / "test.esq"
            good.write_text('<SequenceQueue version="2.6"><Job><Count>1</Count></Job></SequenceQueue>')
            self.assertEqual(bridge.validate_plan_file("capture_load_sequence", {"path": str(good)}, setup), str(good))
            bad = root / "script.esq"
            bad.write_text('<SequenceQueue><PreCaptureScript>/tmp/action.sh</PreCaptureScript></SequenceQueue>')
            with self.assertRaises(ValueError):
                bridge.validate_plan_file("capture_load_sequence", {"path": str(bad)}, setup)
            outside = Path(tmp) / "outside.esq"
            outside.write_text('<SequenceQueue/>')
            with self.assertRaises(ValueError):
                bridge.validate_plan_file("capture_load_sequence", {"path": str(outside)}, setup)
            bad.write_text('<SchedulerList><Profile>Profile</Profile><ShutdownProcedure><Procedure>ParkMount</Procedure></ShutdownProcedure></SchedulerList>')
            scheduler = root / "park.esl"
            scheduler.write_text(bad.read_text())
            with self.assertRaises(ValueError):
                bridge.validate_plan_file("scheduler_load", {"path": str(scheduler)}, setup)


    def test_control_does_not_allow_solar_tracking(self):
        with patch.object(bridge, "upstream") as upstream:
            request = {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": "mount_set_track_mode", "arguments": {"mode": "solar"}}}
            self.assertIn("error", bridge.handle(request, "test", control=True))
            upstream.assert_not_called()


if __name__ == "__main__":
    unittest.main()
