using DMA.Application.Encounters;
using DMA.Domain.Enums;
using DMA.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;

namespace DMA.Tests;

public class EncounterServiceTests
{
    private static AppDbContext CreateDb()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;
        return new AppDbContext(options);
    }

    [Fact]
    public async Task StartAsync_OrdersParticipantsByInitiativeDescending()
    {
        await using var db = CreateDb();
        var service = new EncounterService(db);

        var campaign = new DMA.Domain.Entities.Campaign { Name = "Test Campaign" };
        db.Campaigns.Add(campaign);
        await db.SaveChangesAsync();

        var encounter = await service.CreateAsync(campaign.Id, "Goblin Ambush", null);
        await service.AddCustomAsync(encounter.Id, "Slow Guy", initiative: 5, maxHp: 10, armorClass: 12);
        await service.AddCustomAsync(encounter.Id, "Fast Guy", initiative: 18, maxHp: 8, armorClass: 14);
        await service.AddCustomAsync(encounter.Id, "Medium Guy", initiative: 10, maxHp: 12, armorClass: 13);

        await service.StartAsync(encounter.Id);

        var result = await service.GetByIdAsync(encounter.Id);

        Assert.NotNull(result);
        Assert.Equal(EncounterStatus.Active, result!.Status);
        Assert.Equal(1, result.CurrentRound);
        var ordered = result.Participants.OrderBy(p => p.SortOrder).Select(p => p.Name).ToList();
        Assert.Equal(["Fast Guy", "Medium Guy", "Slow Guy"], ordered);
    }

    [Fact]
    public async Task NextTurnAsync_AdvancesTurnAndWrapsRound()
    {
        await using var db = CreateDb();
        var service = new EncounterService(db);

        var campaign = new DMA.Domain.Entities.Campaign { Name = "Test Campaign" };
        db.Campaigns.Add(campaign);
        await db.SaveChangesAsync();

        var encounter = await service.CreateAsync(campaign.Id, "Goblin Ambush", null);
        await service.AddCustomAsync(encounter.Id, "A", initiative: 20, maxHp: 10, armorClass: 12);
        await service.AddCustomAsync(encounter.Id, "B", initiative: 10, maxHp: 10, armorClass: 12);
        await service.StartAsync(encounter.Id);

        await service.NextTurnAsync(encounter.Id);
        var afterFirst = await service.GetByIdAsync(encounter.Id);
        var current = afterFirst!.Participants.OrderBy(p => p.SortOrder).ElementAt(afterFirst.CurrentTurnIndex);
        Assert.Equal("B", current.Name);
        Assert.Equal(1, afterFirst.CurrentRound);

        await service.NextTurnAsync(encounter.Id);
        var afterSecond = await service.GetByIdAsync(encounter.Id);
        var currentAgain = afterSecond!.Participants.OrderBy(p => p.SortOrder).ElementAt(afterSecond.CurrentTurnIndex);
        Assert.Equal("A", currentAgain.Name);
        Assert.Equal(2, afterSecond.CurrentRound);
    }

    [Fact]
    public async Task NextTurnAsync_SkipsInactiveParticipants()
    {
        await using var db = CreateDb();
        var service = new EncounterService(db);

        var campaign = new DMA.Domain.Entities.Campaign { Name = "Test Campaign" };
        db.Campaigns.Add(campaign);
        await db.SaveChangesAsync();

        var encounter = await service.CreateAsync(campaign.Id, "Goblin Ambush", null);
        await service.AddCustomAsync(encounter.Id, "A", initiative: 20, maxHp: 10, armorClass: 12);
        var b = await service.AddCustomAsync(encounter.Id, "B", initiative: 15, maxHp: 10, armorClass: 12);
        await service.AddCustomAsync(encounter.Id, "C", initiative: 10, maxHp: 10, armorClass: 12);
        await service.StartAsync(encounter.Id);
        await service.SetActiveAsync(b.Id, isActive: false);

        await service.NextTurnAsync(encounter.Id);

        var result = await service.GetByIdAsync(encounter.Id);
        var current = result!.Participants.OrderBy(p => p.SortOrder).ElementAt(result.CurrentTurnIndex);
        Assert.Equal("C", current.Name);
    }
}
