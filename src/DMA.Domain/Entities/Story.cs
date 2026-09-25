namespace DMA.Domain.Entities;

/// <summary>
/// A reusable, campaign-independent plot outline the DM writes once — a tree of StoryNodes — and
/// can attach (as a deep copy, see CampaignStoryNode) to any number of campaigns.
/// </summary>
public class Story
{
    public int Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public List<StoryNode> Nodes { get; set; } = new();
}
