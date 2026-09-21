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

    [Fact]
    public void Clamp_KeepsScoresWithinConfiguredBounds()
    {
        var abilities = new AbilityScores
        {
            Strength = 500,
            Dexterity = -500,
            Constitution = 50,
            Intelligence = 100,
            Wisdom = -100,
            Charisma = 0
        };

        abilities.Clamp();

        Assert.Equal(AbilityScores.MaxScore, abilities.Strength);
        Assert.Equal(AbilityScores.MinScore, abilities.Dexterity);
        Assert.Equal(50, abilities.Constitution);
        Assert.Equal(AbilityScores.MaxScore, abilities.Intelligence);
        Assert.Equal(AbilityScores.MinScore, abilities.Wisdom);
        Assert.Equal(0, abilities.Charisma);
    }
}
