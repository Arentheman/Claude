namespace DMA.Domain.Entities;

/// <summary>
/// One node in a master Story's plot tree — a scene, a decision point, a branch. Belongs to the
/// reusable Story template, never to a specific campaign (see CampaignStoryNode for that).
/// </summary>
public class StoryNode
{
    public int Id { get; set; }
    public int StoryId { get; set; }
    public Story Story { get; set; } = null!;

    public int? ParentNodeId { get; set; }
    public StoryNode? ParentNode { get; set; }
    public List<StoryNode> Children { get; set; } = new();

    public string Title { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string PlannedEncounters { get; set; } = string.Empty;
    public string PlannedLoot { get; set; } = string.Empty;
    public int SortOrder { get; set; }
}
