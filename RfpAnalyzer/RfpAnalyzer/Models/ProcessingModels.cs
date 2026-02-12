namespace RfpAnalyzer.Models;

public enum QueueItemStatus
{
    Pending,
    Processing,
    Completed,
    Failed
}

public class QueueItem
{
    public string Id { get; set; } = "";
    public string Name { get; set; } = "";
    public string ItemType { get; set; } = "";
    public QueueItemStatus Status { get; set; } = QueueItemStatus.Pending;
    public DateTime? StartTime { get; set; }
    public DateTime? EndTime { get; set; }
    public double? Duration { get; set; }
    public string? ErrorMessage { get; set; }
    public object? Result { get; set; }
    public Dictionary<string, object> Metadata { get; set; } = new();

    public void Start()
    {
        Status = QueueItemStatus.Processing;
        StartTime = DateTime.UtcNow;
    }

    public void Complete(object? result = null)
    {
        Status = QueueItemStatus.Completed;
        EndTime = DateTime.UtcNow;
        if (StartTime.HasValue)
            Duration = (EndTime.Value - StartTime.Value).TotalSeconds;
        Result = result;
    }

    public void Fail(string errorMessage)
    {
        Status = QueueItemStatus.Failed;
        EndTime = DateTime.UtcNow;
        if (StartTime.HasValue)
            Duration = (EndTime.Value - StartTime.Value).TotalSeconds;
        ErrorMessage = errorMessage;
    }

    public double GetElapsedTime()
    {
        if (Duration.HasValue) return Duration.Value;
        if (StartTime.HasValue) return (DateTime.UtcNow - StartTime.Value).TotalSeconds;
        return 0.0;
    }

    public string GetStatusIcon() => Status switch
    {
        QueueItemStatus.Pending => "⏳",
        QueueItemStatus.Processing => "🔄",
        QueueItemStatus.Completed => "✅",
        QueueItemStatus.Failed => "❌",
        _ => "❓"
    };
}

public class ProcessingQueue
{
    public string Name { get; set; } = "";
    public List<QueueItem> Items { get; set; } = new();
    public DateTime? StartTime { get; set; }
    public DateTime? EndTime { get; set; }

    public QueueItem AddItem(string id, string name, string itemType, Dictionary<string, object>? metadata = null)
    {
        var item = new QueueItem
        {
            Id = id,
            Name = name,
            ItemType = itemType,
            Metadata = metadata ?? new()
        };
        Items.Add(item);
        return item;
    }

    public void Start() => StartTime = DateTime.UtcNow;
    public void Finish() => EndTime = DateTime.UtcNow;

    public QueueItem? GetItem(string id) => Items.FirstOrDefault(i => i.Id == id);
    public List<QueueItem> GetPendingItems() => Items.Where(i => i.Status == QueueItemStatus.Pending).ToList();
    public List<QueueItem> GetCompletedItems() => Items.Where(i => i.Status == QueueItemStatus.Completed).ToList();
    public List<QueueItem> GetFailedItems() => Items.Where(i => i.Status == QueueItemStatus.Failed).ToList();

    public (int Total, int Completed, int Failed, int Processing, int Pending, int Percentage) GetProgress()
    {
        int total = Items.Count;
        int completed = Items.Count(i => i.Status == QueueItemStatus.Completed);
        int failed = Items.Count(i => i.Status == QueueItemStatus.Failed);
        int processing = Items.Count(i => i.Status == QueueItemStatus.Processing);
        int pending = Items.Count(i => i.Status == QueueItemStatus.Pending);
        int percentage = total > 0 ? (int)((completed + failed) * 100.0 / total) : 0;
        return (total, completed, failed, processing, pending, percentage);
    }

    public double GetTotalDuration()
    {
        if (!StartTime.HasValue) return 0.0;
        if (EndTime.HasValue) return (EndTime.Value - StartTime.Value).TotalSeconds;
        return (DateTime.UtcNow - StartTime.Value).TotalSeconds;
    }

    public double GetAverageItemDuration()
    {
        var completed = Items.Where(i => i.Duration.HasValue).ToList();
        if (completed.Count == 0) return 0.0;
        return completed.Average(i => i.Duration!.Value);
    }

    public bool IsComplete => Items.All(i => i.Status == QueueItemStatus.Completed || i.Status == QueueItemStatus.Failed);

    public void Clear()
    {
        Items.Clear();
        StartTime = null;
        EndTime = null;
    }
}

public static class DurationFormatter
{
    public static string Format(double seconds)
    {
        if (seconds < 1) return $"{seconds * 1000:F0}ms";
        if (seconds < 60) return $"{seconds:F1}s";
        int minutes = (int)(seconds / 60);
        double remaining = seconds % 60;
        return $"{minutes}m {remaining:F1}s";
    }
}
