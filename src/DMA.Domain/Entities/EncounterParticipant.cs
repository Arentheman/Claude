using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

public class EncounterParticipant
{
    public int Id { get; set; }
    public int EncounterId { get; set; }
    public Encounter Encounter { get; set; } = null!;

    public ParticipantSourceType SourceType { get; set; } = ParticipantSourceType.Custom;

    /// <summary>Id of the PlayerCharacter or StatBlock this participant was cloned from, if any.</summary>
    public int? SourceId { get; set; }

    public string Name { get; set; } = string.Empty;
    public int Initiative { get; set; }
    public int MaxHp { get; set; }
    public int CurrentHp { get; set; }
    public int ArmorClass { get; set; }

    /// <summary>Active conditions, e.g. "Poisoned", "Prone". Stored as JSON via value converter.</summary>
    public List<string> Conditions { get; set; } = new();

    public bool IsActive { get; set; } = true;
    public int SortOrder { get; set; }
}
