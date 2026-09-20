namespace DMA.Application.Common.Interfaces;

/// <summary>
/// Abstraction over where uploaded files (portraits, attachments) live on disk, so the
/// Application layer never depends on a concrete file system path or IWebHostEnvironment.
/// </summary>
public interface IFileStorageService
{
    /// <summary>Saves the stream under a new generated name and returns that stored name.</summary>
    Task<string> SaveAsync(Stream content, string originalFileName, CancellationToken ct = default);

    void Delete(string storedFileName);
}
