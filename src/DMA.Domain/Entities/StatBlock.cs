using System.ComponentModel.DataAnnotations;
using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

/// <summary>A reusable bestiary entry: a monster or NPC template that can be cloned into an encounter.</summary>
public class StatBlock
{
    public int Id { get; set; }

    public string Name { get; set; } = string.Empty;
    public StatBlockType Type { get; set; } = StatBlockType.Monster;
    public string? ChallengeRating { get; set; }

    [Range(0, int.MaxValue, ErrorMessage = "HP не может быть отрицательным.")]
    public int MaxHp { get; set; }

    [Range(0, int.MaxValue, ErrorMessage = "AC не может быть отрицательным.")]
    public int ArmorClass { get; set; }

    public string Speed { get; set; } = "30 ft.";

    public AbilityScores Abilities { get; set; } = new();

    public string Description { get; set; } = string.Empty;
    public string Source { get; set; } = "Custom";
}
