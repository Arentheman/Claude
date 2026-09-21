using System.ComponentModel.DataAnnotations;

namespace DMA.Domain.Entities;

public class PlayerCharacter
{
    public int Id { get; set; }
    public int CampaignId { get; set; }
    public Campaign Campaign { get; set; } = null!;

    public string Name { get; set; } = string.Empty;
    public string PlayerName { get; set; } = string.Empty;
    public string Race { get; set; } = string.Empty;
    public string Class { get; set; } = string.Empty;

    [Range(1, int.MaxValue, ErrorMessage = "Уровень не может быть меньше 1.")]
    public int Level { get; set; } = 1;

    [Range(0, int.MaxValue, ErrorMessage = "HP не может быть отрицательным.")]
    public int MaxHp { get; set; }

    [Range(0, int.MaxValue, ErrorMessage = "HP не может быть отрицательным.")]
    public int CurrentHp { get; set; }

    [Range(0, int.MaxValue, ErrorMessage = "AC не может быть отрицательным.")]
    public int ArmorClass { get; set; }

    public AbilityScores Abilities { get; set; } = new();
    public Currency Currency { get; set; } = new();

    /// <summary>Stored file name of the portrait (see IFileStorageService), or null if none set.</summary>
    public string? PortraitPath { get; set; }

    public string Notes { get; set; } = string.Empty;

    /// <summary>Persistent conditions (Poisoned, Exhaustion, ...) that last beyond a single
    /// encounter, shown on the campaign quick panel. Stored as JSON via value converter.</summary>
    public List<string> Conditions { get; set; } = new();

    public List<InventoryItem> Inventory { get; set; } = new();
    public List<CharacterFeature> Features { get; set; } = new();
    public List<CharacterAttachment> Attachments { get; set; } = new();
}
