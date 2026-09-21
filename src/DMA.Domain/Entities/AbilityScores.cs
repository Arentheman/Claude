using System.ComponentModel.DataAnnotations;

namespace DMA.Domain.Entities;

/// <summary>Owned value object: the six D&amp;D ability scores.</summary>
public class AbilityScores
{
    public const int MinScore = -100;
    public const int MaxScore = 100;

    private const string RangeError = "Значение должно быть от -100 до 100.";

    [Range(MinScore, MaxScore, ErrorMessage = RangeError)]
    public int Strength { get; set; } = 10;

    [Range(MinScore, MaxScore, ErrorMessage = RangeError)]
    public int Dexterity { get; set; } = 10;

    [Range(MinScore, MaxScore, ErrorMessage = RangeError)]
    public int Constitution { get; set; } = 10;

    [Range(MinScore, MaxScore, ErrorMessage = RangeError)]
    public int Intelligence { get; set; } = 10;

    [Range(MinScore, MaxScore, ErrorMessage = RangeError)]
    public int Wisdom { get; set; } = 10;

    [Range(MinScore, MaxScore, ErrorMessage = RangeError)]
    public int Charisma { get; set; } = 10;

    public static int Modifier(int score) => (int)Math.Floor((score - 10) / 2.0);

    public void Clamp()
    {
        Strength = Math.Clamp(Strength, MinScore, MaxScore);
        Dexterity = Math.Clamp(Dexterity, MinScore, MaxScore);
        Constitution = Math.Clamp(Constitution, MinScore, MaxScore);
        Intelligence = Math.Clamp(Intelligence, MinScore, MaxScore);
        Wisdom = Math.Clamp(Wisdom, MinScore, MaxScore);
        Charisma = Math.Clamp(Charisma, MinScore, MaxScore);
    }
}
