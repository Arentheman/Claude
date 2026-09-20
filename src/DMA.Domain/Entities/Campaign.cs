using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

public class Campaign
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public CampaignStatus Status { get; set; } = CampaignStatus.Active;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public List<Session> Sessions { get; set; } = new();
    public List<PlayerCharacter> PlayerCharacters { get; set; } = new();
    public List<Encounter> Encounters { get; set; } = new();
}
