using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Common.Interfaces;

/// <summary>
/// Abstraction over persistence used by the Application layer, so it never depends on a
/// concrete EF Core provider (SQLite locally, PostgreSQL when deployed).
/// </summary>
public interface IApplicationDbContext
{
    DbSet<Campaign> Campaigns { get; }
    DbSet<Session> Sessions { get; }
    DbSet<PlayerCharacter> PlayerCharacters { get; }
    DbSet<InventoryItem> InventoryItems { get; }
    DbSet<CharacterFeature> CharacterFeatures { get; }
    DbSet<CharacterAttachment> CharacterAttachments { get; }
    DbSet<StatBlock> StatBlocks { get; }
    DbSet<Encounter> Encounters { get; }
    DbSet<EncounterParticipant> EncounterParticipants { get; }
    DbSet<Story> Stories { get; }
    DbSet<StoryNode> StoryNodes { get; }
    DbSet<CampaignStoryNode> CampaignStoryNodes { get; }

    Task<int> SaveChangesAsync(CancellationToken cancellationToken = default);
}
