using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

public class Campaign
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public CampaignStatus Status { get; set; } = CampaignStatus.Active;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    /// <summary>The master Story this campaign's plot tree was copied from, if any. Kept only to
    /// know which template to offer updates from — the campaign's own tree (CampaignStoryNodes)
    /// is a fully independent copy, not a live reference.</summary>
    public int? SourceStoryId { get; set; }
    public Story? SourceStory { get; set; }

    public List<Session> Sessions { get; set; } = new();
    public List<PlayerCharacter> PlayerCharacters { get; set; } = new();
    public List<Encounter> Encounters { get; set; } = new();
    public List<CampaignStoryNode> StoryNodes { get; set; } = new();
}
