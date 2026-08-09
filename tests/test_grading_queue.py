import threading
import time
import unittest

from grading_queue import GradingQueue, GradingQueueFull


class GradingQueueTests(unittest.TestCase):
    def test_waiting_jobs_are_run_in_fifo_order(self):
        queue = GradingQueue(max_concurrent=1, max_queued=3)
        release_first = threading.Event()
        started_first = threading.Event()
        order = []
        results = []

        def first():
            started_first.set()
            release_first.wait(2)
            order.append("first")
            return "first"

        def second():
            order.append("second")
            return "second"

        first_thread = threading.Thread(target=lambda: results.append(queue.submit(first)[0]))
        second_thread = threading.Thread(target=lambda: results.append(queue.submit(second)[0]))
        first_thread.start()
        self.assertTrue(started_first.wait(1))
        second_thread.start()
        release_first.set()
        first_thread.join(2)
        second_thread.join(2)

        self.assertEqual(order, ["first", "second"])
        self.assertCountEqual(results, ["first", "second"])

    def test_full_waiting_room_is_rejected(self):
        queue = GradingQueue(max_concurrent=1, max_queued=1)
        release_first = threading.Event()
        started_first = threading.Event()

        def blocked():
            started_first.set()
            release_first.wait(2)

        first_thread = threading.Thread(target=lambda: queue.submit(blocked))
        first_thread.start()
        self.assertTrue(started_first.wait(1))
        second_thread = threading.Thread(target=lambda: queue.submit(lambda: None))
        second_thread.start()
        for _ in range(100):
            if queue.stats()["waiting"] == 1:
                break
            time.sleep(0.01)
        self.assertEqual(queue.stats()["waiting"], 1)
        with self.assertRaises(GradingQueueFull):
            queue.submit(lambda: None)
        release_first.set()
        first_thread.join(2)
        second_thread.join(2)

    def test_start_cooldown_spaces_out_parallel_workers(self):
        queue = GradingQueue(max_concurrent=2, max_queued=2)
        started_at = []
        lock = threading.Lock()

        def work():
            with lock:
                started_at.append(time.monotonic())

        first = threading.Thread(target=lambda: queue.submit(work, start_cooldown_seconds=0.03))
        second = threading.Thread(target=lambda: queue.submit(work, start_cooldown_seconds=0.03))
        first.start()
        second.start()
        first.join(2)
        second.join(2)

        self.assertEqual(len(started_at), 2)
        self.assertGreaterEqual(abs(started_at[1] - started_at[0]), 0.02)
