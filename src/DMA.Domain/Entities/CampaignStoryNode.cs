using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

/// <summary>
/// A campaign's own working copy of one plot node, created by deep-copying a Story's node tree
/// when the DM attaches that story to this campaign (see CampaignStoryService.AttachStoryAsync).
/// Fully independent afterwards: play-time edits and progress here never write back to the
/// master Story, and master edits never flow in automatically — the DM pulls specific updates in
/// manually via SourceStoryNodeId (see CampaignStoryService.PullNodeAsync), by design, to avoid
/// auto-merge ever clobbering notes made during a live session.
/// </summary>
public class CampaignStoryNode
{
    public int Id { get; set; }
    public int CampaignId { get; set; }
    public Campaign Campaign { get; set; } = null!;

    public int? ParentNodeId { get; set; }
    public CampaignStoryNode? ParentNode { get; set; }
    public List<CampaignStoryNode> Children { get; set; } = new();

    /// <summary>The master StoryNode this was copied from, if any — used only to find updates
    /// available to manually pull in later. Null for nodes the DM added directly in the campaign.</summary>
    public int? SourceStoryNodeId { get; set; }

    public string Title { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public string PlannedLoot { get; set; } = string.Empty;
    public int SortOrder { get; set; }

    public StoryNodeStatus Status { get; set; } = StoryNodeStatus.Planned;
}
