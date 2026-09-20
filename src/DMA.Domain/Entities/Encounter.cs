using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

public class Encounter
{
    public int Id { get; set; }
    public int CampaignId { get; set; }
    public Campaign Campaign { get; set; } = null!;

    public int? SessionId { get; set; }
    public Session? Session { get; set; }

    public string Name { get; set; } = string.Empty;
    public EncounterStatus Status { get; set; } = EncounterStatus.Planned;

    public int CurrentRound { get; set; } = 1;
    public int CurrentTurnIndex { get; set; } = 0;

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public List<EncounterParticipant> Participants { get; set; } = new();
}
