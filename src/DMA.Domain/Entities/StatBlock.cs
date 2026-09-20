using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

/// <summary>A reusable bestiary entry: a monster or NPC template that can be cloned into an encounter.</summary>
public class StatBlock
{
    public int Id { get; set; }

    public string Name { get; set; } = string.Empty;
    public StatBlockType Type { get; set; } = StatBlockType.Monster;
    public string? ChallengeRating { get; set; }

    public int MaxHp { get; set; }
    public int ArmorClass { get; set; }
    public string Speed { get; set; } = "30 ft.";

    public AbilityScores Abilities { get; set; } = new();

    public string Description { get; set; } = string.Empty;
    public string Source { get; set; } = "Custom";
}
