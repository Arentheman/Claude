namespace DMA.Application.Common.Interfaces;

/// <summary>
/// Exports the whole app's data (all campaigns, characters, bestiary, uploaded images) as a
/// single downloadable file, and restores it later — a manual "save file" workflow that lets
/// someone move between machines or keep a backup without needing hosting or accounts.
/// </summary>
public interface IBackupService
{
    /// <summary>Builds a .dmasave (zip) snapshot of the current database and uploaded files.</summary>
    Task<Stream> ExportAsync(CancellationToken ct = default);

    /// <summary>
    /// Replaces ALL current data with the contents of the given .dmasave file. Destructive and
    /// not reversible — the caller is responsible for confirming with the user first.
    /// </summary>
    Task ImportAsync(Stream backupFileStream, CancellationToken ct = default);
}
