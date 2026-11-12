import importlib.util
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PY = Path(__file__).resolve().parent.parent / "python"


def load(name):
    spec = importlib.util.spec_from_file_location(name, PY / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


log_analyzer = load("log_analyzer")
release_gate = load("release_gate")
ssl_cert_expiry = load("ssl_cert_expiry")
disk_alert = load("disk_usage_alert")

SAMPLE_LOG = """\
10.0.0.1 - - [10/Oct/2026:13:55:36 +0000] "GET /api/orders HTTP/1.1" 200 512 "-" "curl/8" 0.120
10.0.0.1 - - [10/Oct/2026:13:55:40 +0000] "GET /api/orders?id=1 HTTP/1.1" 200 512 "-" "curl/8" 0.100
10.0.0.2 - - [10/Oct/2026:13:56:01 +0000] "POST /api/pay HTTP/1.1" 500 90 "-" "curl/8" 1.900
10.0.0.2 - - [10/Oct/2026:13:56:02 +0000] "POST /api/pay HTTP/1.1" 502 90 "-" "curl/8" 2.100
10.0.0.3 - - [10/Oct/2026:13:56:03 +0000] "GET /health HTTP/1.1" 200 2 "-" "kube-probe" 0.001
this line is not a log line
"""


class LogAnalyzer(unittest.TestCase):
    def test_summary(self):
        r = log_analyzer.analyse(SAMPLE_LOG.splitlines())
        self.assertEqual(r["total_requests"], 5)
        self.assertEqual(r["unparsed_lines"], 1)
        self.assertEqual(r["status_classes"], {"2xx": 3, "5xx": 2})
        self.assertEqual(r["error_rate_pct"], 40.0)
        self.assertEqual(r["top_5xx_paths"][0], ("/api/pay", 2))
        self.assertEqual(r["worst_5xx_minute"], ("10/Oct/2026:13:56", 2))
        self.assertEqual(r["p95_request_time_s"], 2.1)

    def test_query_string_is_stripped(self):
        lines = ['1.1.1.1 - - [10/Oct/2026:13:55:36 +0000] "GET /a?x=1 HTTP/1.1" 500 1 "-" "-"']
        self.assertEqual(log_analyzer.analyse(lines)["top_5xx_paths"], [("/a", 1)])

    def test_cli_exit_code_on_threshold(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as fh:
            fh.write(SAMPLE_LOG)
        try:
            r = subprocess.run([sys.executable, str(PY / "log_analyzer.py"), fh.name, "--max-error-rate", "5"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
        finally:
            os.unlink(fh.name)


class ReleaseGate(unittest.TestCase):
    def test_passes_after_consecutive_healthy_rounds(self):
        calls = iter([(True, "ok")] * 3)
        ok = release_gate.gate(["u"], checks=3, interval=0, timeout=5, check=lambda *a: next(calls),
                               sleep=lambda s: None, log=lambda m: None)
        self.assertTrue(ok)

    def test_failure_resets_the_streak(self):
        seq = iter([(True, "ok"), (True, "ok"), (False, "bad"), (True, "ok"), (True, "ok"), (True, "ok")])
        ok = release_gate.gate(["u"], checks=3, interval=0, timeout=5, check=lambda *a: next(seq),
                               sleep=lambda s: None, log=lambda m: None)
        self.assertTrue(ok)  # needs 3 in a row after the failure

    def test_times_out_when_never_healthy(self):
        t = {"now": 0.0}
        ok = release_gate.gate(["u"], checks=2, interval=1, timeout=5,
                               check=lambda *a: (False, "down"),
                               sleep=lambda s: t.__setitem__("now", t["now"] + s),
                               clock=lambda: t["now"], log=lambda m: None)
        self.assertFalse(ok)

    def test_real_http_server(self):
        class H(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200 if self.path == "/health" else 500)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            self.assertTrue(release_gate.gate([base + "/health"], checks=2, interval=0.05, timeout=5, log=lambda m: None))
            self.assertFalse(release_gate.gate([base + "/broken"], checks=2, interval=0.05, timeout=0.3, log=lambda m: None))
        finally:
            srv.shutdown()
            srv.server_close()


@unittest.skipUnless(shutil.which("openssl"), "openssl not installed")
class SslExpiry(unittest.TestCase):
    def test_reads_expiry_from_local_tls_server(self):
        with tempfile.TemporaryDirectory() as d:
            key, crt = f"{d}/k.pem", f"{d}/c.pem"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt,
                            "-days", "10", "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost"],
                           check=True, capture_output=True)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(crt, key)
            srv = HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler)
            srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            try:
                days = ssl_cert_expiry.days_remaining("localhost", srv.server_address[1], cafile=crt)
                self.assertTrue(9 < days <= 10, days)
            finally:
                srv.shutdown()
                srv.server_close()

    def test_classify(self):
        self.assertEqual(ssl_cert_expiry.classify(100, 30, 14), ("OK", 0))
        self.assertEqual(ssl_cert_expiry.classify(20, 30, 14), ("WARNING", 1))
        self.assertEqual(ssl_cert_expiry.classify(5, 30, 14), ("CRITICAL", 2))
        self.assertEqual(ssl_cert_expiry.classify(-1, 30, 14), ("EXPIRED", 2))

    def test_split_target(self):
        self.assertEqual(ssl_cert_expiry.split_target("a.com"), ("a.com", 443))
        self.assertEqual(ssl_cert_expiry.split_target("a.com:8443"), ("a.com", 8443))


class DiskAlert(unittest.TestCase):
    def test_thresholds(self):
        with tempfile.TemporaryDirectory() as d:
            r = disk_alert.check_mount(d, warn=0, crit=101)
            self.assertEqual(r["status"], "WARNING")
            self.assertEqual(disk_alert.check_mount(d, 101, 102)["status"], "OK")


class ShellScripts(unittest.TestCase):
    SHELL = PY.parent / "shell"

    def test_log_cleanup_dry_run_then_execute(self):
        with tempfile.TemporaryDirectory() as d:
            old = Path(d) / "old.log"
            new = Path(d) / "new.log"
            old.write_text("x"), new.write_text("y")
            os.utime(old, (1, 1))  # 1970
            dry = subprocess.run(["bash", str(self.SHELL / "log_cleanup.sh"), "-d", d, "-a", "7"], capture_output=True, text=True)
            self.assertIn("dry-run", dry.stdout)
            self.assertTrue(old.exists())
            subprocess.run(["bash", str(self.SHELL / "log_cleanup.sh"), "-d", d, "-a", "7", "-x"], check=True, capture_output=True)
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())

    def test_log_cleanup_refuses_system_dirs(self):
        r = subprocess.run(["bash", str(self.SHELL / "log_cleanup.sh"), "-d", "/etc"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_shell_syntax(self):
        for s in self.SHELL.glob("*.sh"):
            self.assertEqual(subprocess.run(["bash", "-n", str(s)]).returncode, 0, s.name)


if __name__ == "__main__":
    unittest.main()
