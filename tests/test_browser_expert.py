import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import auth_vault  # noqa: E402
import har_to_client  # noqa: E402
import preflight_guard  # noqa: E402


class TestBrowserExpert(unittest.TestCase):
    def test_auth_vault_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get("BROWSER_VAULT_DIR")
            os.environ["BROWSER_VAULT_DIR"] = tmp
            try:
                rc = auth_vault.main(["init", "demo-portal", "--url", "https://example.com"])
                self.assertEqual(rc, 0)
                self.assertTrue((Path(tmp) / "demo-portal" / "chrome-profile").is_dir())
                self.assertEqual(auth_vault.main(["profile", "demo-portal"]), 0)
                self.assertEqual(auth_vault.main(["remove", "demo-portal"]), 0)
                self.assertFalse((Path(tmp) / "demo-portal").exists())
            finally:
                if old is None:
                    os.environ.pop("BROWSER_VAULT_DIR", None)
                else:
                    os.environ["BROWSER_VAULT_DIR"] = old

    def test_har_distillation_filters_noise_and_secrets(self):
        sample_har = {
            "log": {
                "entries": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "https://www.google-analytics.com/collect?v=1",
                            "headers": [],
                        },
                        "response": {"status": 200, "content": {"mimeType": "image/gif"}},
                    },
                    {
                        "request": {
                            "method": "GET",
                            "url": "https://api.example.com/static/app.js",
                            "headers": [],
                        },
                        "response": {"status": 200, "content": {"mimeType": "application/javascript"}},
                    },
                    {
                        "request": {
                            "method": "POST",
                            "url": "https://api.example.com/v1/orders?page=1",
                            "headers": [
                                {"name": "Authorization", "value": "Bearer SUPER_SECRET_TOKEN"},
                                {"name": "Content-Type", "value": "application/json"},
                            ],
                        },
                        "response": {"status": 201, "content": {"mimeType": "application/json"}},
                    },
                ]
            }
        }
        endpoints = har_to_client.distill_har(sample_har, domain_filter="example.com")
        self.assertEqual(len(endpoints), 1)
        ep = endpoints[0]
        self.assertEqual(ep["method"], "POST")
        self.assertEqual(ep["path"], "/v1/orders")
        self.assertEqual(ep["required_auth_headers"], ["Authorization"])
        code = har_to_client.generate_client_code(endpoints)
        self.assertNotIn("SUPER_SECRET_TOKEN", code)
        self.assertIn("def post_v1_orders(", code)

    def test_preflight_guard_classifications(self):
        plan = [
            {"type": "navigate", "target": "https://example.com/orders", "description": "open list"},
            {"type": "click", "target": "@e12", "description": "点击提交审批按钮"},
            {"type": "click", "target": "@e99", "description": "solve recaptcha automatically"},
        ]
        res = preflight_guard.evaluate_plan(plan)
        self.assertEqual(res["verdict"], "BLOCKED")
        self.assertEqual(res["counts"], {"READ": 1, "WRITE_CONFIRM": 1, "BLOCKED": 1})


if __name__ == "__main__":
    unittest.main()
