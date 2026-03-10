"""Tests for services.processing_queue module."""

import time
import pytest

from services.processing_queue import (
    QueueItem,
    QueueItemStatus,
    ProcessingQueue,
    format_duration,
)


# ============================================================================
# QueueItem tests
# ============================================================================

class TestQueueItem:
    """Tests for the QueueItem dataclass."""

    def _make_item(self, **kwargs) -> QueueItem:
        defaults = {"id": "test-1", "name": "Test Item", "item_type": "rfp"}
        defaults.update(kwargs)
        return QueueItem(**defaults)

    def test_initial_status_is_pending(self):
        item = self._make_item()
        assert item.status == QueueItemStatus.PENDING

    def test_start_sets_processing(self):
        item = self._make_item()
        item.start()
        assert item.status == QueueItemStatus.PROCESSING
        assert item.start_time is not None

    def test_complete_sets_completed(self):
        item = self._make_item()
        item.start()
        item.complete(result="some_result")
        assert item.status == QueueItemStatus.COMPLETED
        assert item.result == "some_result"
        assert item.duration is not None
        assert item.duration >= 0

    def test_fail_sets_failed(self):
        item = self._make_item()
        item.start()
        item.fail("Something went wrong")
        assert item.status == QueueItemStatus.FAILED
        assert item.error_message == "Something went wrong"
        assert item.duration is not None

    def test_get_elapsed_time_when_pending(self):
        item = self._make_item()
        assert item.get_elapsed_time() == 0.0

    def test_get_elapsed_time_while_processing(self):
        item = self._make_item()
        item.start()
        elapsed = item.get_elapsed_time()
        assert elapsed >= 0.0

    def test_get_elapsed_time_after_completion(self):
        item = self._make_item()
        item.start()
        item.complete()
        elapsed = item.get_elapsed_time()
        assert elapsed == item.duration

    def test_status_icons(self):
        item = self._make_item()
        assert item.get_status_icon() == "⏳"
        item.start()
        assert item.get_status_icon() == "🔄"
        item.complete()
        assert item.get_status_icon() == "✅"

    def test_status_icon_failed(self):
        item = self._make_item()
        item.start()
        item.fail("err")
        assert item.get_status_icon() == "❌"

    def test_to_dict(self):
        item = self._make_item(metadata={"key": "val"})
        d = item.to_dict()
        assert d["id"] == "test-1"
        assert d["name"] == "Test Item"
        assert d["item_type"] == "rfp"
        assert d["status"] == "pending"
        assert d["metadata"] == {"key": "val"}

    def test_to_dict_after_complete(self):
        item = self._make_item()
        item.start()
        item.complete(result="ok")
        d = item.to_dict()
        assert d["status"] == "completed"
        assert d["duration"] is not None


# ============================================================================
# ProcessingQueue tests
# ============================================================================

class TestProcessingQueue:
    """Tests for the ProcessingQueue dataclass."""

    def _make_queue(self, n_items: int = 3) -> ProcessingQueue:
        queue = ProcessingQueue(name="Test Queue")
        for i in range(n_items):
            queue.add_item(id=f"item-{i}", name=f"Item {i}", item_type="test")
        return queue

    def test_add_item(self):
        queue = ProcessingQueue(name="Q")
        item = queue.add_item(id="x", name="X", item_type="rfp")
        assert len(queue.items) == 1
        assert item.id == "x"

    def test_get_item(self):
        queue = self._make_queue()
        item = queue.get_item("item-1")
        assert item is not None
        assert item.name == "Item 1"

    def test_get_item_missing(self):
        queue = self._make_queue()
        assert queue.get_item("nonexistent") is None

    def test_get_pending_items(self):
        queue = self._make_queue()
        assert len(queue.get_pending_items()) == 3

    def test_get_completed_items(self):
        queue = self._make_queue()
        queue.items[0].start()
        queue.items[0].complete()
        assert len(queue.get_completed_items()) == 1

    def test_get_failed_items(self):
        queue = self._make_queue()
        queue.items[0].start()
        queue.items[0].fail("err")
        assert len(queue.get_failed_items()) == 1

    def test_progress(self):
        queue = self._make_queue(n_items=4)
        queue.items[0].start()
        queue.items[0].complete()
        queue.items[1].start()
        queue.items[1].fail("err")
        progress = queue.get_progress()
        assert progress["total"] == 4
        assert progress["completed"] == 1
        assert progress["failed"] == 1
        assert progress["processing"] == 0
        assert progress["pending"] == 2
        assert progress["percentage"] == 50  # (1+1)/4 * 100

    def test_progress_empty_queue(self):
        queue = ProcessingQueue(name="Empty")
        progress = queue.get_progress()
        assert progress["total"] == 0
        assert progress["percentage"] == 0

    def test_is_complete(self):
        queue = self._make_queue(n_items=2)
        assert not queue.is_complete()
        queue.items[0].start()
        queue.items[0].complete()
        assert not queue.is_complete()
        queue.items[1].start()
        queue.items[1].fail("err")
        assert queue.is_complete()

    def test_start_and_finish_timing(self):
        queue = self._make_queue()
        queue.start()
        assert queue.start_time is not None
        assert queue.get_total_duration() > 0
        queue.finish()
        assert queue.end_time is not None
        duration = queue.get_total_duration()
        assert duration >= 0

    def test_get_total_duration_before_start(self):
        queue = self._make_queue()
        assert queue.get_total_duration() == 0.0

    def test_get_average_item_duration(self):
        queue = self._make_queue(n_items=2)
        queue.items[0].start()
        queue.items[0].complete()
        queue.items[1].start()
        queue.items[1].complete()
        avg = queue.get_average_item_duration()
        assert avg >= 0

    def test_get_average_item_duration_empty(self):
        queue = self._make_queue()
        assert queue.get_average_item_duration() == 0.0

    def test_clear(self):
        queue = self._make_queue()
        queue.start()
        queue.clear()
        assert len(queue.items) == 0
        assert queue.start_time is None
        assert queue.end_time is None

    def test_to_dict(self):
        queue = self._make_queue(n_items=1)
        queue.start()
        d = queue.to_dict()
        assert d["name"] == "Test Queue"
        assert len(d["items"]) == 1
        assert "progress" in d
        assert "total_duration" in d

    def test_add_item_with_metadata(self):
        queue = ProcessingQueue(name="Q")
        item = queue.add_item(
            id="x", name="X", item_type="rfp",
            metadata={"filename": "test.pdf", "size": 1024}
        )
        assert item.metadata["filename"] == "test.pdf"
        assert item.metadata["size"] == 1024


# ============================================================================
# format_duration (processing_queue version)
# ============================================================================

class TestProcessingQueueFormatDuration:
    """Test format_duration from processing_queue module."""

    def test_sub_second(self):
        result = format_duration(0.5)
        assert "ms" in result or "s" in result

    def test_seconds(self):
        assert format_duration(30.0) == "30.0s"

    def test_minutes(self):
        result = format_duration(90.0)
        assert "1m" in result
