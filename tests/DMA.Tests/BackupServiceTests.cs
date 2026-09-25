using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using DMA.Infrastructure.Backup;
using DMA.Infrastructure.Data;
using Microsoft.EntityFrameworkCore;

namespace DMA.Tests;

/// <summary>
/// Export/import relies on real SQLite behavior (WAL checkpointing, on-disk file copies,
/// cascade-delete foreign keys), none of which the InMemory provider used elsewhere in this
/// suite actually exercises — so these tests use real temp SQLite database files.
/// </summary>
public class BackupServiceTests : IDisposable
{
    private readonly DirectoryInfo _tempDir = Directory.CreateTempSubdirectory("dma-backup-test-");

    private sealed class FakeFileStorageService(string rootPath) : IFileStorageService
    {
        public string RootPath { get; } = rootPath;
        public Task<string> SaveAsync(Stream content, string originalFileName, CancellationToken ct = default)
            => throw new NotSupportedException();
        public void Delete(string storedFileName) => throw new NotSupportedException();
    }

    private async Task<AppDbContext> CreateMigratedDbAsync(string dbPath)
    {
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlite($"Data Source={dbPath}")
            .Options;
        var db = new AppDbContext(options);
        await db.Database.MigrateAsync();
        return db;
    }

    [Fact]
    public async Task ExportThenImport_RoundTripsDataAndUploadedFiles()
    {
        var dbPath = Path.Combine(_tempDir.FullName, "dungeonmaster.db");
        var uploadsPath = Path.Combine(_tempDir.FullName, "uploads");
        Directory.CreateDirectory(uploadsPath);
        var portraitFileName = "portrait-abc123.png";
        await File.WriteAllBytesAsync(Path.Combine(uploadsPath, portraitFileName), [1, 2, 3, 4]);

        await using var db = await CreateMigratedDbAsync(dbPath);
        var fileStorage = new FakeFileStorageService(uploadsPath);
        var backupService = new BackupService(db, fileStorage);

        var campaign = new Campaign { Name = "Lost Mines" };
        db.Campaigns.Add(campaign);
        await db.SaveChangesAsync();

        var character = new PlayerCharacter
        {
            CampaignId = campaign.Id,
            Name = "Thalia",
            Race = "Elf",
            Class = "Wizard",
            Level = 3,
            MaxHp = 18,
            CurrentHp = 12,
            ArmorClass = 13,
            PortraitPath = portraitFileName
        };
        character.Inventory.Add(new InventoryItem { Name = "Wand of Magic Missiles", Quantity = 1 });
        db.PlayerCharacters.Add(character);

        var statBlock = new StatBlock { Name = "Goblin", MaxHp = 7, ArmorClass = 15 };
        db.StatBlocks.Add(statBlock);

        await db.SaveChangesAsync();

        await using var exportStream = await backupService.ExportAsync();

        // Wipe live data + uploads to simulate a fresh install before importing.
        db.Campaigns.RemoveRange(db.Campaigns);
        db.StatBlocks.RemoveRange(db.StatBlocks);
        await db.SaveChangesAsync();
        foreach (var file in Directory.GetFiles(uploadsPath))
            File.Delete(file);

        exportStream.Position = 0;
        await backupService.ImportAsync(exportStream);

        var restoredCampaign = await db.Campaigns
            .Include(c => c.PlayerCharacters).ThenInclude(pc => pc.Inventory)
            .SingleAsync();
        Assert.Equal("Lost Mines", restoredCampaign.Name);

        var restoredCharacter = Assert.Single(restoredCampaign.PlayerCharacters);
        Assert.Equal("Thalia", restoredCharacter.Name);
        Assert.Equal(3, restoredCharacter.Level);
        Assert.Equal(portraitFileName, restoredCharacter.PortraitPath);
        Assert.Single(restoredCharacter.Inventory);
        Assert.Equal("Wand of Magic Missiles", restoredCharacter.Inventory[0].Name);

        var restoredStatBlock = await db.StatBlocks.SingleAsync();
        Assert.Equal("Goblin", restoredStatBlock.Name);

        var restoredFile = Path.Combine(uploadsPath, portraitFileName);
        Assert.True(File.Exists(restoredFile));
        Assert.Equal(new byte[] { 1, 2, 3, 4 }, await File.ReadAllBytesAsync(restoredFile));
    }

    [Fact]
    public async Task ImportAsync_RejectsFileThatIsNotAZip()
    {
        var dbPath = Path.Combine(_tempDir.FullName, "dungeonmaster.db");
        var uploadsPath = Path.Combine(_tempDir.FullName, "uploads");
        Directory.CreateDirectory(uploadsPath);

        await using var db = await CreateMigratedDbAsync(dbPath);
        var backupService = new BackupService(db, new FakeFileStorageService(uploadsPath));

        using var notAZip = new MemoryStream([0x00, 0x01, 0x02, 0x03]);

        await Assert.ThrowsAsync<InvalidOperationException>(() => backupService.ImportAsync(notAZip));
    }

    public void Dispose()
    {
        try { _tempDir.Delete(recursive: true); } catch { /* best-effort cleanup */ }
    }
}
