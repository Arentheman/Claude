using System.ComponentModel.DataAnnotations;
using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

/// <summary>A spell or class/racial ability belonging to a player character.</summary>
public class CharacterFeature
{
    public int Id { get; set; }
    public int PlayerCharacterId { get; set; }
    public PlayerCharacter PlayerCharacter { get; set; } = null!;

    public string Name { get; set; } = string.Empty;
    public CharacterFeatureType Type { get; set; } = CharacterFeatureType.Ability;

    /// <summary>Spell level (0 = cantrip, 9 = highest). Meaningless for Type = Ability.</summary>
    [Range(0, 9, ErrorMessage = "Уровень заклинания от 0 (заговор) до 9.")]
    public int? Level { get; set; }

    public string Description { get; set; } = string.Empty;
}
