import threading
import time
import unittest

from core.paralelo import run_parallel
from core.procesador import WebProcessor
from core.red import DomainRateLimiter, RateLimiter, fetch_bounded
from tests.helpers import LocalServer


class RateLimiterTests(unittest.TestCase):
    def test_spacing_without_serializing_the_wait_under_lock(self):
        limiter = RateLimiter(0.1)
        starts = []

        def call():
            limiter.wait()
            starts.append(time.monotonic())

        threads = [threading.Thread(target=call) for _ in range(4)]
        t0 = time.monotonic()
        [t.start() for t in threads]
        [t.join() for t in threads]
        starts.sort()
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertTrue(all(g >= 0.08 for g in gaps), gaps)
        self.assertLess(time.monotonic() - t0, 0.6)

    def test_stop_event_aborts_wait(self):
        limiter, stop = RateLimiter(5.0), threading.Event()
        limiter.wait()
        threading.Timer(0.1, stop.set).start()
        t0 = time.monotonic()
        self.assertFalse(limiter.wait(stop))
        self.assertLess(time.monotonic() - t0, 1.0)


class FetchBoundedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__()

    def fetch(self, path, **kw):
        kw.setdefault("max_bytes", 2_000_000)
        kw.setdefault("attempts", 1)
        return fetch_bounded(self.server.base + path, **kw)

    def test_ok(self):
        res = self.fetch("/a")
        self.assertTrue(res.ok)
        self.assertGreater(len(res.content), 1000)

    def test_declared_size_over_limit_is_rejected_before_reading(self):
        self.assertEqual(self.fetch("/big").reason, "too_large")

    def test_streaming_without_content_length_is_cut_at_limit(self):
        res = self.fetch("/bigstream", max_bytes=500_000)
        self.assertEqual(res.reason, "too_large")
        self.assertEqual(res.content, b"")

    def test_total_timeout_beats_slow_dripping_server(self):
        t0 = time.monotonic()
        res = self.fetch("/slow", total_timeout=0.7)
        self.assertEqual(res.reason, "timeout")
        self.assertLess(time.monotonic() - t0, 3)

    def test_http_error_and_skip_if(self):
        self.assertEqual(self.fetch("/nada").reason, "http_404")
        res = self.fetch("/pdf", skip_if=lambda h: "pdf_skipped" if "pdf" in h.get("Content-Type", "") else None)
        self.assertEqual(res.reason, "pdf_skipped")


class ProcessorEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LocalServer().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.server.__exit__()

    def setUp(self):
        self.p = WebProcessor(rate_limiter=DomainRateLimiter(0), retries=1)

    def test_real_page_is_extracted_with_quality(self):
        item = self.p.scrape_url_details(self.server.base + "/a")
        self.assertEqual(item["reason"], "ok")
        self.assertEqual(item["title"], "Página a")
        self.assertIn("# Página a", item["content"])
        self.assertNotIn("Copyright", item["content"])
        self.assertNotIn("Inicio Blog", item["content"])
        self.assertGreaterEqual(item["quality"], 70)
        self.assertEqual(len(item["sha256"]), 64)

    def test_junk_page_has_low_quality_or_no_content(self):
        item = self.p.scrape_url_details(self.server.base + "/junk")
        self.assertLess(item["quality"], 50)

    def test_pdf_skipped_unless_allowed(self):
        self.assertEqual(self.p.scrape_url_details(self.server.base + "/pdf")["reason"], "pdf_skipped")

    def test_max_chars_truncates_at_line_boundary(self):
        p = WebProcessor(rate_limiter=DomainRateLimiter(0), retries=1, max_chars=2000)
        item = p.scrape_url_details(self.server.base + "/a")
        self.assertTrue(item["truncated"])
        self.assertLessEqual(len(item["content"]), 2000)
        self.assertTrue(item["content"].rstrip().endswith("."))


class RunParallelTests(unittest.TestCase):
    def test_order_errors_and_progress(self):
        seen = []

        def work(x):
            if x == 3:
                raise ValueError("boom")
            return x * 2

        res = run_parallel(range(6), work, max_workers=3, progress=lambda d, t, l: seen.append((d, t)),
                           on_error=lambda item, exc: -1)
        self.assertEqual(res, [0, 2, 4, -1, 8, 10])
        self.assertEqual(seen[-1], (6, 6))

    def test_stop_returns_quickly_with_partial_results(self):
        stop = threading.Event()
        threading.Timer(0.3, stop.set).start()
        t0 = time.monotonic()
        res = run_parallel(range(20), lambda x: (time.sleep(1), x)[1], max_workers=2, stop_event=stop)
        self.assertLess(time.monotonic() - t0, 2)
        self.assertIn(None, res)


if __name__ == "__main__":
    unittest.main()
