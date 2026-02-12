using RfpAnalyzer.Models;

namespace RfpAnalyzer.Tests.Models;

public class DurationFormatterTests
{
    [Theory]
    [InlineData(0.5, "500ms")]
    [InlineData(0.001, "1ms")]
    [InlineData(0.999, "999ms")]
    public void Format_SubSecond_ReturnsMilliseconds(double seconds, string expected)
    {
        Assert.Equal(expected, DurationFormatter.Format(seconds));
    }

    [Theory]
    [InlineData(1.0, "1.0s")]
    [InlineData(5.5, "5.5s")]
    [InlineData(59.9, "59.9s")]
    public void Format_Seconds_ReturnsSeconds(double seconds, string expected)
    {
        Assert.Equal(expected, DurationFormatter.Format(seconds));
    }

    [Theory]
    [InlineData(60, "1m 0.0s")]
    [InlineData(90, "1m 30.0s")]
    [InlineData(125.5, "2m 5.5s")]
    public void Format_Minutes_ReturnsMinutesAndSeconds(double seconds, string expected)
    {
        Assert.Equal(expected, DurationFormatter.Format(seconds));
    }
}
