"""
Processing Queue for Document Extraction and Proposal Scoring.

This module provides queue-based processing with progress tracking and timing.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import time


class QueueItemStatus(str, Enum):
    """Status of a queue item."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QueueItem:
    """Represents an item in the processing queue."""
    id: str
    name: str
    item_type: str  # "rfp", "proposal", "evaluation"
    status: QueueItemStatus = QueueItemStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: Optional[float] = None
    error_message: Optional[str] = None
    result: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def start(self):
        """Mark the item as processing."""
        self.status = QueueItemStatus.PROCESSING
        self.start_time = time.time()
    
    def complete(self, result: Any = None):
        """Mark the item as completed."""
        self.status = QueueItemStatus.COMPLETED
        self.end_time = time.time()
        if self.start_time:
            self.duration = self.end_time - self.start_time
        self.result = result
    
    def fail(self, error_message: str):
        """Mark the item as failed."""
        self.status = QueueItemStatus.FAILED
        self.end_time = time.time()
        if self.start_time:
            self.duration = self.end_time - self.start_time
        self.error_message = error_message
    
    def get_elapsed_time(self) -> float:
        """Get the elapsed time for this item."""
        if self.duration is not None:
            return self.duration
        if self.start_time is not None:
            return time.time() - self.start_time
        return 0.0
    
    def get_status_icon(self) -> str:
        """Get a status icon for display."""
        icons = {
            QueueItemStatus.PENDING: "⏳",
            QueueItemStatus.PROCESSING: "🔄",
            QueueItemStatus.COMPLETED: "✅",
            QueueItemStatus.FAILED: "❌"
        }
        return icons.get(self.status, "❓")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "item_type": self.item_type,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "error_message": self.error_message,
            "metadata": self.metadata
        }


@dataclass
class ProcessingQueue:
    """Manages a queue of items to be processed."""
    name: str
    items: List[QueueItem] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    def add_item(self, id: str, name: str, item_type: str, metadata: Optional[Dict[str, Any]] = None) -> QueueItem:
        """Add an item to the queue."""
        item = QueueItem(
            id=id,
            name=name,
            item_type=item_type,
            metadata=metadata or {}
        )
        self.items.append(item)
        return item
    
    def start(self):
        """Mark the queue as started."""
        self.start_time = time.time()
    
    def finish(self):
        """Mark the queue as finished."""
        self.end_time = time.time()
    
    def get_item(self, id: str) -> Optional[QueueItem]:
        """Get an item by ID."""
        for item in self.items:
            if item.id == id:
                return item
        return None
    
    def get_pending_items(self) -> List[QueueItem]:
        """Get all pending items."""
        return [item for item in self.items if item.status == QueueItemStatus.PENDING]
    
    def get_completed_items(self) -> List[QueueItem]:
        """Get all completed items."""
        return [item for item in self.items if item.status == QueueItemStatus.COMPLETED]
    
    def get_failed_items(self) -> List[QueueItem]:
        """Get all failed items."""
        return [item for item in self.items if item.status == QueueItemStatus.FAILED]
    
    def get_progress(self) -> Dict[str, Any]:
        """Get overall progress statistics."""
        total = len(self.items)
        completed = len([i for i in self.items if i.status == QueueItemStatus.COMPLETED])
        failed = len([i for i in self.items if i.status == QueueItemStatus.FAILED])
        processing = len([i for i in self.items if i.status == QueueItemStatus.PROCESSING])
        pending = len([i for i in self.items if i.status == QueueItemStatus.PENDING])
        
        percentage = int((completed + failed) / total * 100) if total > 0 else 0
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "processing": processing,
            "pending": pending,
            "percentage": percentage
        }
    
    def get_total_duration(self) -> float:
        """Get total queue processing duration."""
        if self.start_time is None:
            return 0.0
        if self.end_time is not None:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def get_average_item_duration(self) -> float:
        """Get average duration per completed item."""
        completed = [i for i in self.items if i.duration is not None]
        if not completed:
            return 0.0
        return sum(i.duration for i in completed) / len(completed)
    
    def is_complete(self) -> bool:
        """Check if all items are processed (completed or failed)."""
        return all(
            item.status in [QueueItemStatus.COMPLETED, QueueItemStatus.FAILED]
            for item in self.items
        )
    
    def clear(self):
        """Clear all items from the queue."""
        self.items.clear()
        self.start_time = None
        self.end_time = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "items": [item.to_dict() for item in self.items],
            "start_time": self.start_time,
            "end_time": self.end_time,
            "progress": self.get_progress(),
            "total_duration": self.get_total_duration()
        }


def format_duration(seconds: float) -> str:
    """Format duration in a human-readable way."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
