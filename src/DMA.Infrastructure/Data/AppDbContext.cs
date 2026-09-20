using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace DMA.Infrastructure.Data;

public class AppDbContext(DbContextOptions<AppDbContext> options) : DbContext(options), IApplicationDbContext
{
    public DbSet<Campaign> Campaigns => Set<Campaign>();
    public DbSet<Session> Sessions => Set<Session>();
    public DbSet<PlayerCharacter> PlayerCharacters => Set<PlayerCharacter>();
    public DbSet<InventoryItem> InventoryItems => Set<InventoryItem>();
    public DbSet<StatBlock> StatBlocks => Set<StatBlock>();
    public DbSet<Encounter> Encounters => Set<Encounter>();
    public DbSet<EncounterParticipant> EncounterParticipants => Set<EncounterParticipant>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(AppDbContext).Assembly);
        base.OnModelCreating(modelBuilder);
    }
}
