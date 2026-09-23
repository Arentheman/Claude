using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Stories;

/// <summary>Manages the reusable, campaign-independent Story library — the master plot trees DMs
/// write once and later attach (as a deep copy) to any number of campaigns.</summary>
public class StoryService(IApplicationDbContext db)
{
    public Task<List<Story>> GetAllAsync(CancellationToken ct = default) =>
        db.Stories.OrderByDescending(s => s.CreatedAt).ToListAsync(ct);

    public Task<Story?> GetByIdAsync(int id, CancellationToken ct = default) =>
        db.Stories.FirstOrDefaultAsync(s => s.Id == id, ct);

    /// <summary>Flat, tracked list — EF's relationship fixup wires up each node's Children/ParentNode
    /// navigation automatically since every node of the story is loaded into the same context.</summary>
    public Task<List<StoryNode>> GetNodesAsync(int storyId, CancellationToken ct = default) =>
        db.StoryNodes.Where(n => n.StoryId == storyId).OrderBy(n => n.SortOrder).ToListAsync(ct);

    public async Task<Story> CreateAsync(string name, string description, CancellationToken ct = default)
    {
        var story = new Story { Name = name, Description = description };
        db.Stories.Add(story);
        await db.SaveChangesAsync(ct);
        return story;
    }

    public async Task UpdateAsync(Story story, CancellationToken ct = default)
    {
        db.Stories.Update(story);
        await db.SaveChangesAsync(ct);
    }

    public async Task DeleteAsync(int id, CancellationToken ct = default)
    {
        var story = await db.Stories.FindAsync([id], ct);
        if (story is null) return;
        db.Stories.Remove(story);
        await db.SaveChangesAsync(ct);
    }

    public async Task<StoryNode> AddNodeAsync(int storyId, int? parentNodeId, string title, CancellationToken ct = default)
    {
        var node = new StoryNode
        {
            StoryId = storyId,
            ParentNodeId = parentNodeId,
            Title = title,
            SortOrder = await NextSortOrderAsync(storyId, parentNodeId, ct)
        };
        db.StoryNodes.Add(node);
        await db.SaveChangesAsync(ct);
        return node;
    }

    public async Task UpdateNodeAsync(
        int nodeId, string title, string description, string plannedEncounters, string plannedLoot,
        CancellationToken ct = default)
    {
        var node = await db.StoryNodes.FindAsync([nodeId], ct);
        if (node is null) return;
        node.Title = title;
        node.Description = description;
        node.PlannedEncounters = plannedEncounters;
        node.PlannedLoot = plannedLoot;
        await db.SaveChangesAsync(ct);
    }

    /// <summary>Deletes a node and its whole subtree. ParentNodeId is a Restrict FK, so the
    /// descendants are loaded and removed together — EF orders the DELETEs itself once every
    /// affected row is tracked in the same SaveChanges call.</summary>
    public async Task DeleteNodeAsync(int nodeId, CancellationToken ct = default)
    {
        var node = await db.StoryNodes.FindAsync([nodeId], ct);
        if (node is null) return;

        var storyNodes = await db.StoryNodes.Where(n => n.StoryId == node.StoryId).ToListAsync(ct);
        db.StoryNodes.RemoveRange(CollectSubtree(storyNodes, nodeId));
        await db.SaveChangesAsync(ct);
    }

    private async Task<int> NextSortOrderAsync(int storyId, int? parentNodeId, CancellationToken ct)
    {
        var max = await db.StoryNodes
            .Where(n => n.StoryId == storyId && n.ParentNodeId == parentNodeId)
            .Select(n => (int?)n.SortOrder)
            .MaxAsync(ct);
        return (max ?? -1) + 1;
    }

    private static List<StoryNode> CollectSubtree(List<StoryNode> all, int rootId)
    {
        var byParent = all.ToLookup(n => n.ParentNodeId);
        var result = new List<StoryNode>();
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
