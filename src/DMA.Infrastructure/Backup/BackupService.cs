using System.IO.Compression;
using System.Text.Json;
using DMA.Application.Common.Interfaces;
using DMA.Infrastructure.Data;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;

namespace DMA.Infrastructure.Backup;

/// <summary>
/// Export is a low-risk snapshot: checkpoint the WAL so the on-disk file is complete and
/// consistent, then copy it byte-for-byte alongside the uploads folder into a zip.
///
/// Import is the risky direction (it destroys whatever is currently there), so it never touches
/// the live database file directly. Instead it opens the uploaded backup as a second, independent
/// SQLite database, reads everything out of it through EF, and only then wipes and re-populates
/// the live database inside a transaction — so a bad or corrupt backup file fails loudly before
/// anything real is deleted. The uploads folder is swapped only after that transaction commits.
/// </summary>
public class BackupService(AppDbContext db, IFileStorageService fileStorage) : IBackupService
{
    private const string DbFileNameInZip = "dungeonmaster.db";
    private const string UploadsFolderNameInZip = "uploads";
    private const string ManifestFileNameInZip = "manifest.json";

    public async Task<Stream> ExportAsync(CancellationToken ct = default)
    {
        EnsureSqlite();
        var liveDbPath = GetLiveDbFilePath();

        // Flush any pending write-ahead-log data into the main file so the copy below is complete.
        await db.Database.ExecuteSqlRawAsync("PRAGMA wal_checkpoint(TRUNCATE);", ct);

        var stagingDir = Directory.CreateTempSubdirectory("dma-export-");
        var zipPath = stagingDir.FullName + ".dmasave";
        try
        {
            File.Copy(liveDbPath, Path.Combine(stagingDir.FullName, DbFileNameInZip));

            if (Directory.Exists(fileStorage.RootPath))
                CopyDirectoryContents(fileStorage.RootPath, Path.Combine(stagingDir.FullName, UploadsFolderNameInZip));

            var manifest = new
            {
                ExportedAtUtc = DateTime.UtcNow,
                Campaigns = await db.Campaigns.CountAsync(ct),
                PlayerCharacters = await db.PlayerCharacters.CountAsync(ct),
                StatBlocks = await db.StatBlocks.CountAsync(ct),
                Stories = await db.Stories.CountAsync(ct)
            };
            await File.WriteAllTextAsync(
                Path.Combine(stagingDir.FullName, ManifestFileNameInZip),
                JsonSerializer.Serialize(manifest, new JsonSerializerOptions { WriteIndented = true }),
                ct);

            ZipFile.CreateFromDirectory(stagingDir.FullName, zipPath);

            // Hand back an in-memory copy so the temp file can be cleaned up before returning.
            var bytes = await File.ReadAllBytesAsync(zipPath, ct);
            return new MemoryStream(bytes);
        }
        finally
        {
            stagingDir.Delete(recursive: true);
            if (File.Exists(zipPath))
                File.Delete(zipPath);
        }
    }

    public async Task ImportAsync(Stream backupFileStream, CancellationToken ct = default)
    {
        EnsureSqlite();

        var stagingDir = Directory.CreateTempSubdirectory("dma-import-");
        var zipPath = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.zip");
        try
        {
            await using (var fileStream = File.Create(zipPath))
                await backupFileStream.CopyToAsync(fileStream, ct);

            try
            {
                ZipFile.ExtractToDirectory(zipPath, stagingDir.FullName);
            }
            catch (InvalidDataException ex)
            {
                throw new InvalidOperationException("Файл не похож на сохранение приложения — это не архив.", ex);
            }

            var importedDbPath = Path.Combine(stagingDir.FullName, DbFileNameInZip);
            if (!File.Exists(importedDbPath))
                throw new InvalidOperationException("Файл не похож на сохранение приложения — не найдена база данных внутри архива.");

            var snapshot = await ReadSnapshotAsync(importedDbPath, ct);

            await using var transaction = await db.Database.BeginTransactionAsync(ct);
            try
            {
                // Deleting the three root tables cascades (at the SQLite foreign-key level) to
                // every child table, so this alone empties the whole database. Stories is its own
                // root — it isn't reachable from Campaigns or StatBlocks — but Campaign.SourceStoryId
                // is ON DELETE SET NULL, so the order between these three doesn't matter.
                await db.Database.ExecuteSqlRawAsync("DELETE FROM \"Campaigns\";", ct);
                await db.Database.ExecuteSqlRawAsync("DELETE FROM \"StatBlocks\";", ct);
                await db.Database.ExecuteSqlRawAsync("DELETE FROM \"Stories\";", ct);

                // Stories first and alone: Campaigns.SourceStoryId references it, and inserts are
                // only guaranteed FK-safe across separate SaveChanges calls in this codebase (see
                // the class doc) — never by relying on same-call ordering for entities carrying
                // already-assigned keys.
                db.Stories.AddRange(snapshot.Stories);
                await db.SaveChangesAsync(ct);

                db.Campaigns.AddRange(snapshot.Campaigns);
                db.StatBlocks.AddRange(snapshot.StatBlocks);
                await db.SaveChangesAsync(ct);

                db.Sessions.AddRange(snapshot.Sessions);
                db.PlayerCharacters.AddRange(snapshot.PlayerCharacters);
                db.Encounters.AddRange(snapshot.Encounters);
                // Parent-before-child within this same call relies on Id ascending order already
                // matching tree depth (ReadSnapshotAsync orders by Id; the app always creates a
                // parent node before any of its children, so parent Id < child Id by construction).
                db.StoryNodes.AddRange(snapshot.StoryNodes);
                await db.SaveChangesAsync(ct);

                db.InventoryItems.AddRange(snapshot.InventoryItems);
                db.CharacterFeatures.AddRange(snapshot.CharacterFeatures);
                db.CharacterAttachments.AddRange(snapshot.CharacterAttachments);
                db.EncounterParticipants.AddRange(snapshot.EncounterParticipants);
                // Same parent-before-child reasoning as StoryNodes above, plus this depends on
                // StoryNodes (nullable SourceStoryNodeId) already committed in the tier above.
                db.CampaignStoryNodes.AddRange(snapshot.CampaignStoryNodes);
                await db.SaveChangesAsync(ct);

                await transaction.CommitAsync(ct);
            }
            catch
            {
                await transaction.RollbackAsync(ct);
                throw;
            }

            // Only swap uploaded files once the database import has safely committed.
            if (Directory.Exists(fileStorage.RootPath))
            {
                foreach (var file in Directory.GetFiles(fileStorage.RootPath))
                    File.Delete(file);
            }
            var importedUploads = Path.Combine(stagingDir.FullName, UploadsFolderNameInZip);
            if (Directory.Exists(importedUploads))
                CopyDirectoryContents(importedUploads, fileStorage.RootPath);
        }
        finally
        {
            stagingDir.Delete(recursive: true);
            if (File.Exists(zipPath))
                File.Delete(zipPath);
        }
    }

    private static async Task<ImportedSnapshot> ReadSnapshotAsync(string importedDbPath, CancellationToken ct)
    {
        // Pooling=False is required here: Microsoft.Data.Sqlite pools the native connection by
        // default, which keeps an OS-level handle on importedDbPath open even after this context
        // is disposed. On Windows that handle blocks the temp-folder cleanup in ImportAsync's
        // finally block ("file in use by another process"); Linux doesn't enforce that lock, so
        // this only surfaces on Windows. Disabling pooling for this short-lived context closes
        // the file for good on Dispose.
        var connectionString = $"Data Source={importedDbPath};Pooling=False";
        var options = new DbContextOptionsBuilder<AppDbContext>()
            .UseSqlite(connectionString)
            .Options;

        try
        {
            await using var source = new AppDbContext(options);
            return new ImportedSnapshot(
                Campaigns: await source.Campaigns.AsNoTracking().ToListAsync(ct),
                StatBlocks: await source.StatBlocks.AsNoTracking().ToListAsync(ct),
                Sessions: await source.Sessions.AsNoTracking().ToListAsync(ct),
                PlayerCharacters: await source.PlayerCharacters.AsNoTracking().ToListAsync(ct),
                Encounters: await source.Encounters.AsNoTracking().ToListAsync(ct),
                InventoryItems: await source.InventoryItems.AsNoTracking().ToListAsync(ct),
                CharacterFeatures: await source.CharacterFeatures.AsNoTracking().ToListAsync(ct),
                CharacterAttachments: await source.CharacterAttachments.AsNoTracking().ToListAsync(ct),
                EncounterParticipants: await source.EncounterParticipants.AsNoTracking().ToListAsync(ct),
                Stories: await source.Stories.AsNoTracking().ToListAsync(ct),
                // Ascending Id order guarantees parent-before-child within these self-referencing
                // tables, since the app always creates a parent node before any of its children.
                StoryNodes: await source.StoryNodes.AsNoTracking().OrderBy(n => n.Id).ToListAsync(ct),
                CampaignStoryNodes: await source.CampaignStoryNodes.AsNoTracking().OrderBy(n => n.Id).ToListAsync(ct));
        }
        catch (Exception ex)
        {
            throw new InvalidOperationException(
                "Не удалось прочитать базу данных из файла сохранения — он повреждён или сделан несовместимой версией приложения.", ex);
        }
    }

    private void EnsureSqlite()
    {
        if (db.Database.ProviderName?.Contains("Sqlite", StringComparison.OrdinalIgnoreCase) != true)
            throw new NotSupportedException("Экспорт/импорт файлом сохранения работает только с локальной базой SQLite.");
    }

    private string GetLiveDbFilePath()
    {
        var connectionString = db.Database.GetConnectionString()
            ?? throw new InvalidOperationException("Не удалось определить путь к файлу базы данных.");

        var dataSource = new SqliteConnectionStringBuilder(connectionString).DataSource;
        return Path.IsPathRooted(dataSource) ? dataSource : Path.GetFullPath(dataSource);
    }

    private static void CopyDirectoryContents(string sourceDir, string targetDir)
    {
        Directory.CreateDirectory(targetDir);
        foreach (var file in Directory.GetFiles(sourceDir))
            File.Copy(file, Path.Combine(targetDir, Path.GetFileName(file)), overwrite: true);
    }

    private record ImportedSnapshot(
        List<Domain.Entities.Campaign> Campaigns,
        List<Domain.Entities.StatBlock> StatBlocks,
        List<Domain.Entities.Session> Sessions,
        List<Domain.Entities.PlayerCharacter> PlayerCharacters,
        List<Domain.Entities.Encounter> Encounters,
        List<Domain.Entities.InventoryItem> InventoryItems,
        List<Domain.Entities.CharacterFeature> CharacterFeatures,
        List<Domain.Entities.CharacterAttachment> CharacterAttachments,
        List<Domain.Entities.EncounterParticipant> EncounterParticipants,
        List<Domain.Entities.Story> Stories,
        List<Domain.Entities.StoryNode> StoryNodes,
        List<Domain.Entities.CampaignStoryNode> CampaignStoryNodes);
}
