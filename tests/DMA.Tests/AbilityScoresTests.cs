using DMA.Domain.Entities;

namespace DMA.Tests;

public class AbilityScoresTests
{
    [Theory]
    [InlineData(1, -5)]
    [InlineData(8, -1)]
    [InlineData(10, 0)]
    [InlineData(11, 0)]
    [InlineData(15, 2)]
    [InlineData(20, 5)]
    public void Modifier_MatchesDndRules(int score, int expected)
    {
        Assert.Equal(expected, AbilityScores.Modifier(score));
    }
}
