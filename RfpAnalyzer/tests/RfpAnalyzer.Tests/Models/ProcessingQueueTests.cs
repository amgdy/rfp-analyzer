using RfpAnalyzer.Models;

namespace RfpAnalyzer.Tests.Models;

public class ProcessingQueueTests
{
    [Fact]
    public void QueueItem_Start_SetsProcessingStatus()
    {
        var item = new QueueItem { Id = "1", Name = "Test", ItemType = "test" };
        item.Start();
        Assert.Equal(QueueItemStatus.Processing, item.Status);
        Assert.NotNull(item.StartTime);
    }

    [Fact]
    public void QueueItem_Complete_SetsCompletedStatusAndDuration()
    {
        var item = new QueueItem { Id = "1", Name = "Test", ItemType = "test" };
        item.Start();
        Thread.Sleep(10);
        item.Complete("result");
        Assert.Equal(QueueItemStatus.Completed, item.Status);
        Assert.NotNull(item.EndTime);
        Assert.NotNull(item.Duration);
        Assert.True(item.Duration > 0);
        Assert.Equal("result", item.Result);
    }

    [Fact]
    public void QueueItem_Fail_SetsFailedStatusAndError()
    {
        var item = new QueueItem { Id = "1", Name = "Test", ItemType = "test" };
        item.Start();
        item.Fail("Something went wrong");
        Assert.Equal(QueueItemStatus.Failed, item.Status);
        Assert.Equal("Something went wrong", item.ErrorMessage);
    }

    [Fact]
    public void QueueItem_GetStatusIcon_ReturnsCorrectIcons()
    {
        var pending = new QueueItem { Id = "1", Name = "T", ItemType = "t" };
        Assert.Equal("⏳", pending.GetStatusIcon());

        pending.Start();
        Assert.Equal("🔄", pending.GetStatusIcon());

        pending.Complete();
        Assert.Equal("✅", pending.GetStatusIcon());

        var failed = new QueueItem { Id = "2", Name = "T", ItemType = "t" };
        failed.Start();
        failed.Fail("err");
        Assert.Equal("❌", failed.GetStatusIcon());
    }

    [Fact]
    public void QueueItem_GetElapsedTime_ReturnsZeroWhenNotStarted()
    {
        var item = new QueueItem { Id = "1", Name = "T", ItemType = "t" };
        Assert.Equal(0.0, item.GetElapsedTime());
    }

    [Fact]
    public void QueueItem_GetElapsedTime_ReturnsDurationWhenCompleted()
    {
        var item = new QueueItem { Id = "1", Name = "T", ItemType = "t" };
        item.Start();
        Thread.Sleep(50);
        item.Complete();
        Assert.True(item.GetElapsedTime() > 0);
    }

    [Fact]
    public void ProcessingQueue_AddItem_AddsToList()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        var item = queue.AddItem("1", "Test Item", "test");
        Assert.Single(queue.Items);
        Assert.Equal("1", item.Id);
        Assert.Equal("Test Item", item.Name);
        Assert.Equal("test", item.ItemType);
    }

    [Fact]
    public void ProcessingQueue_GetItem_FindsById()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        queue.AddItem("1", "First", "test");
        queue.AddItem("2", "Second", "test");

        var found = queue.GetItem("2");
        Assert.NotNull(found);
        Assert.Equal("Second", found.Name);

        var notFound = queue.GetItem("99");
        Assert.Null(notFound);
    }

    [Fact]
    public void ProcessingQueue_GetProgress_ReturnsCorrectCounts()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        var item1 = queue.AddItem("1", "A", "test");
        var item2 = queue.AddItem("2", "B", "test");
        var item3 = queue.AddItem("3", "C", "test");
        var item4 = queue.AddItem("4", "D", "test");

        item1.Start();
        item1.Complete();
        item2.Start();
        item3.Start();
        item3.Fail("err");

        var progress = queue.GetProgress();
        Assert.Equal(4, progress.Total);
        Assert.Equal(1, progress.Completed);
        Assert.Equal(1, progress.Failed);
        Assert.Equal(1, progress.Processing);
        Assert.Equal(1, progress.Pending);
        Assert.Equal(50, progress.Percentage); // (1 completed + 1 failed) / 4 = 50%
    }

    [Fact]
    public void ProcessingQueue_IsComplete_TrueWhenAllDone()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        var item1 = queue.AddItem("1", "A", "test");
        var item2 = queue.AddItem("2", "B", "test");

        Assert.False(queue.IsComplete);

        item1.Start();
        item1.Complete();
        Assert.False(queue.IsComplete);

        item2.Start();
        item2.Fail("err");
        Assert.True(queue.IsComplete);
    }

    [Fact]
    public void ProcessingQueue_Clear_RemovesAllItems()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        queue.Start();
        queue.AddItem("1", "A", "test");
        queue.AddItem("2", "B", "test");

        queue.Clear();
        Assert.Empty(queue.Items);
        Assert.Null(queue.StartTime);
        Assert.Null(queue.EndTime);
    }

    [Fact]
    public void ProcessingQueue_GetTotalDuration_ReturnsZeroWhenNotStarted()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        Assert.Equal(0.0, queue.GetTotalDuration());
    }

    [Fact]
    public void ProcessingQueue_GetAverageItemDuration_ReturnsZeroWithNoCompleted()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        queue.AddItem("1", "A", "test");
        Assert.Equal(0.0, queue.GetAverageItemDuration());
    }

    [Fact]
    public void ProcessingQueue_GetPendingCompletedFailed_FiltersCorrectly()
    {
        var queue = new ProcessingQueue { Name = "Test" };
        var a = queue.AddItem("1", "A", "test");
        var b = queue.AddItem("2", "B", "test");
        var c = queue.AddItem("3", "C", "test");

        a.Start(); a.Complete();
        b.Start(); b.Fail("err");

        Assert.Single(queue.GetCompletedItems());
        Assert.Single(queue.GetFailedItems());
        Assert.Single(queue.GetPendingItems());
    }
}
