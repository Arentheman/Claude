namespace DMA.Domain.Entities;

/// <summary>Owned value object: the six D&amp;D ability scores.</summary>
public class AbilityScores
{
    public int Strength { get; set; } = 10;
    public int Dexterity { get; set; } = 10;
    public int Constitution { get; set; } = 10;
    public int Intelligence { get; set; } = 10;
    public int Wisdom { get; set; } = 10;
    public int Charisma { get; set; } = 10;

    public static int Modifier(int score) => (int)Math.Floor((score - 10) / 2.0);
}
