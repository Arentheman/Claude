using DMA.Application.Characters;
using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using DMA.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;

namespace DMA.Tests;

public class PlayerCharacterServiceTests
{
    private class NoOpFileStorageService : IFileStorageService
    {
        public string RootPath => string.Empty;

        public Task<string> SaveAsync(Stream content, string originalFileName, CancellationToken ct = default) =>
            Task.FromResult("unused.png");

        public void Delete(string storedFileName) { }
    }

    private static AppDbContext CreateDb()
    {
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseInMemoryDatabase(Guid.NewGuid().ToString())
            .Options;
        return new AppDbContext(options);
    }

    [Fact]
    public async Task CreateAsync_ClampsOutOfRangeValuesEvenIfCallerBypassesUiValidation()
    {
        await using var db = CreateDb();
        var service = new PlayerCharacterService(db, new NoOpFileStorageService());

        var campaign = new Campaign { Name = "Test Campaign" };
        db.Campaigns.Add(campaign);
        await db.SaveChangesAsync();

        var character = new PlayerCharacter
        {
            CampaignId = campaign.Id,
            Name = "Hostile Client",
            Level = -5,
            MaxHp = -10,
            CurrentHp = -10,
            ArmorClass = -3,
            Abilities = new AbilityScores { Strength = 999, Dexterity = -999 },
            Currency = new Currency { GoldPieces = -50 }
        };

        var created = await service.CreateAsync(character);

        Assert.Equal(1, created.Level);
        Assert.Equal(0, created.MaxHp);
        Assert.Equal(0, created.CurrentHp);
        Assert.Equal(0, created.ArmorClass);
        Assert.Equal(AbilityScores.MaxScore, created.Abilities.Strength);
        Assert.Equal(AbilityScores.MinScore, created.Abilities.Dexterity);
        Assert.Equal(0, created.Currency.GoldPieces);
    }

    [Fact]
    public async Task AddInventoryItemAsync_ClampsNegativeQuantityToZero()
    {
        await using var db = CreateDb();
        var service = new PlayerCharacterService(db, new NoOpFileStorageService());

        var campaign = new Campaign { Name = "Test Campaign" };
        db.Campaigns.Add(campaign);
        var character = new PlayerCharacter { CampaignId = campaign.Id, Name = "Someone" };
        db.PlayerCharacters.Add(character);
        await db.SaveChangesAsync();

        await service.AddInventoryItemAsync(character.Id, "Rope", -3, "", DMA.Domain.Enums.InventoryItemCategory.Equipment);

        var item = await db.InventoryItems.FirstAsync(i => i.PlayerCharacterId == character.Id);
        Assert.Equal(0, item.Quantity);
    }

    [Fact]
    public async Task ToggleConditionAsync_AddsThenRemovesTheSameCondition()
    {
        await using var db = CreateDb();
        var service = new PlayerCharacterService(db, new NoOpFileStorageService());

        var campaign = new Campaign { Name = "Test Campaign" };
        db.Campaigns.Add(campaign);
        var character = new PlayerCharacter { CampaignId = campaign.Id, Name = "Someone" };
        db.PlayerCharacters.Add(character);
        await db.SaveChangesAsync();

        await service.ToggleConditionAsync(character.Id, "Poisoned");
        var afterAdd = await db.PlayerCharacters.FindAsync(character.Id);
        Assert.Contains("Poisoned", afterAdd!.Conditions);

        await service.ToggleConditionAsync(character.Id, "Poisoned");
        var afterRemove = await db.PlayerCharacters.FindAsync(character.Id);
        Assert.DoesNotContain("Poisoned", afterRemove!.Conditions);
    }

    [Fact]
    public async Task UpdateHpAsync_ClampsToZeroButAllowsExceedingMaxHp()
    {
        await using var db = CreateDb();
        var service = new PlayerCharacterService(db, new NoOpFileStorageService());

        var campaign = new Campaign { Name = "Test Campaign" };
        db.Campaigns.Add(campaign);
        var character = new PlayerCharacter { CampaignId = campaign.Id, Name = "Someone", MaxHp = 20, CurrentHp = 20 };
        db.PlayerCharacters.Add(character);
        await db.SaveChangesAsync();

        await service.UpdateHpAsync(character.Id, -5);
        Assert.Equal(0, (await db.PlayerCharacters.FindAsync(character.Id))!.CurrentHp);

        await service.UpdateHpAsync(character.Id, 25);
        Assert.Equal(25, (await db.PlayerCharacters.FindAsync(character.Id))!.CurrentHp);
    }
}
