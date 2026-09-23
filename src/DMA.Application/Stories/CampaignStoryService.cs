using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using DMA.Domain.Enums;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Stories;

/// <summary>
/// Manages a campaign's own copy of a Story's plot tree. Attaching a story deep-copies it into
/// CampaignStoryNodes — from then on the copy is fully independent: play-time edits here never
/// touch the master Story, and master edits never flow in automatically. The DM pulls specific
/// updates in manually via PullNodeAsync, one node at a time, by design — see CampaignStoryNode's
/// doc comment for why automatic merging was deliberately left out.
/// </summary>
public class CampaignStoryService(IApplicationDbContext db)
{
    public Task<Campaign?> GetCampaignAsync(int campaignId, CancellationToken ct = default) =>
        db.Campaigns.Include(c => c.SourceStory).FirstOrDefaultAsync(c => c.Id == campaignId, ct);

    /// <summary>Flat, tracked list — see StoryService.GetNodesAsync for why this is enough to get
    /// working Children/ParentNode navigation on every node.</summary>
    public Task<List<CampaignStoryNode>> GetNodesAsync(int campaignId, CancellationToken ct = default) =>
        db.CampaignStoryNodes.Where(n => n.CampaignId == campaignId).OrderBy(n => n.SortOrder).ToListAsync(ct);

    public async Task AttachStoryAsync(int campaignId, int storyId, CancellationToken ct = default)
    {
        var campaign = await db.Campaigns.FindAsync([campaignId], ct)
            ?? throw new InvalidOperationException("Кампания не найдена.");
        if (campaign.SourceStoryId is not null)
            throw new InvalidOperationException("К этой кампании уже привязан сюжет — сначала отвяжите текущий.");
        if (!await db.Stories.AnyAsync(s => s.Id == storyId, ct))
            throw new InvalidOperationException("Сюжет не найден.");

        var sourceNodes = await db.StoryNodes.Where(n => n.StoryId == storyId).ToListAsync(ct);

        var copies = sourceNodes.ToDictionary(source => source.Id, source => new CampaignStoryNode
        {
            CampaignId = campaignId,
            SourceStoryNodeId = source.Id,
            Title = source.Title,
            Description = source.Description,
            PlannedEncounters = source.PlannedEncounters,
            PlannedLoot = source.PlannedLoot,
            SortOrder = source.SortOrder,
            Status = StoryNodeStatus.Planned
        });

        // Wire parents via the navigation property, not a raw FK int: none of these rows have a
        // real Id yet, so only EF's own temp-key graph resolution (triggered by AddRange below)
        // can turn this into correct ParentNodeId values, however deep the tree is.
        foreach (var source in sourceNodes)
            if (source.ParentNodeId is int parentId)
                copies[source.Id].ParentNode = copies[parentId];

        db.CampaignStoryNodes.AddRange(copies.Values);
        campaign.SourceStoryId = storyId;
        await db.SaveChangesAsync(ct);
    }

    public async Task DetachStoryAsync(int campaignId, CancellationToken ct = default)
    {
        var campaign = await db.Campaigns.FindAsync([campaignId], ct);
        if (campaign is null) return;

        var nodes = await db.CampaignStoryNodes.Where(n => n.CampaignId == campaignId).ToListAsync(ct);
        db.CampaignStoryNodes.RemoveRange(nodes);
        campaign.SourceStoryId = null;
        await db.SaveChangesAsync(ct);
    }

    public async Task<CampaignStoryNode> AddNodeAsync(int campaignId, int? parentNodeId, string title, CancellationToken ct = default)
    {
        var node = new CampaignStoryNode
        {
            CampaignId = campaignId,
            ParentNodeId = parentNodeId,
            Title = title,
            SortOrder = await NextSortOrderAsync(campaignId, parentNodeId, ct)
        };
        db.CampaignStoryNodes.Add(node);
        await db.SaveChangesAsync(ct);
        return node;
    }

    public async Task UpdateNodeAsync(
        int nodeId, string title, string description, string plannedEncounters, string plannedLoot,
        CancellationToken ct = default)
    {
        var node = await db.CampaignStoryNodes.FindAsync([nodeId], ct);
        if (node is null) return;
        node.Title = title;
        node.Description = description;
        node.PlannedEncounters = plannedEncounters;
        node.PlannedLoot = plannedLoot;
        await db.SaveChangesAsync(ct);
    }

    public async Task SetStatusAsync(int nodeId, StoryNodeStatus status, CancellationToken ct = default)
    {
        var node = await db.CampaignStoryNodes.FindAsync([nodeId], ct);
        if (node is null) return;
        node.Status = status;
        await db.SaveChangesAsync(ct);
    }

    public async Task DeleteNodeAsync(int nodeId, CancellationToken ct = default)
    {
        var node = await db.CampaignStoryNodes.FindAsync([nodeId], ct);
        if (node is null) return;

        var campaignNodes = await db.CampaignStoryNodes.Where(n => n.CampaignId == node.CampaignId).ToListAsync(ct);
        db.CampaignStoryNodes.RemoveRange(CollectSubtree(campaignNodes, nodeId));
        await db.SaveChangesAsync(ct);
    }

    /// <summary>Master nodes of the attached story that have no linked copy in this campaign yet —
    /// candidates to pull in via PullNodeAsync.</summary>
    public async Task<List<StoryNode>> GetPullableNodesAsync(int campaignId, CancellationToken ct = default)
    {
        var campaign = await db.Campaigns.FindAsync([campaignId], ct);
        if (campaign?.SourceStoryId is not int storyId) return [];

        var masterNodes = await db.StoryNodes.Where(n => n.StoryId == storyId).ToListAsync(ct);
        var linkedSourceIds = await db.CampaignStoryNodes
            .Where(n => n.CampaignId == campaignId && n.SourceStoryNodeId != null)
            .Select(n => n.SourceStoryNodeId!.Value)
            .ToListAsync(ct);

        return masterNodes.Where(n => !linkedSourceIds.Contains(n.Id)).ToList();
    }

    /// <summary>
    /// Manually copies one master node's current content into the campaign — the only way content
    /// ever moves from a Story into a campaign after the initial attach. If this master node was
    /// already pulled in before (a CampaignStoryNode links to it via SourceStoryNodeId), its
    /// content is overwritten in place (Status and position are left alone); otherwise a new
    /// linked node is created under targetParentNodeId. This is a plain, explicit overwrite the DM
    /// triggers on purpose — never an automatic diff/merge.
    /// </summary>
    public async Task PullNodeAsync(int campaignId, int storyNodeId, int? targetParentNodeId, CancellationToken ct = default)
    {
        var source = await db.StoryNodes.FindAsync([storyNodeId], ct)
            ?? throw new InvalidOperationException("Узел шаблона не найден.");

        var existing = await db.CampaignStoryNodes
            .FirstOrDefaultAsync(n => n.CampaignId == campaignId && n.SourceStoryNodeId == storyNodeId, ct);

        if (existing is not null)
        {
            existing.Title = source.Title;
            existing.Description = source.Description;
            existing.PlannedEncounters = source.PlannedEncounters;
            existing.PlannedLoot = source.PlannedLoot;
        }
        else
        {
            db.CampaignStoryNodes.Add(new CampaignStoryNode
            {
                CampaignId = campaignId,
                ParentNodeId = targetParentNodeId,
                SourceStoryNodeId = storyNodeId,
                Title = source.Title,
                Description = source.Description,
                PlannedEncounters = source.PlannedEncounters,
                PlannedLoot = source.PlannedLoot,
                SortOrder = await NextSortOrderAsync(campaignId, targetParentNodeId, ct),
                Status = StoryNodeStatus.Planned
            });
        }

        await db.SaveChangesAsync(ct);
    }

    private async Task<int> NextSortOrderAsync(int campaignId, int? parentNodeId, CancellationToken ct)
    {
        var max = await db.CampaignStoryNodes
            .Where(n => n.CampaignId == campaignId && n.ParentNodeId == parentNodeId)
            .Select(n => (int?)n.SortOrder)
            .MaxAsync(ct);
        return (max ?? -1) + 1;
    }

    private static List<CampaignStoryNode> CollectSubtree(List<CampaignStoryNode> all, int rootId)
    {
        var byParent = all.ToLookup(n => n.ParentNodeId);
        var result = new List<CampaignStoryNode>();
        void Walk(int id)
        {
            var node = all.First(n => n.Id == id);
            result.Add(node);
            foreach (var child in byParent[id])
                Walk(child.Id);
        }
        Walk(rootId);
        return result;
    }
}
