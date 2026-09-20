using DMA.Application.Common.Interfaces;
using Microsoft.Extensions.Configuration;

namespace DMA.Infrastructure.Files;

public class FileStorageService : IFileStorageService
{
    private readonly string _rootPath;

    public FileStorageService(IConfiguration configuration)
    {
        var configured = configuration["Storage:UploadsPath"] ?? "uploads";
        _rootPath = Path.IsPathRooted(configured)
            ? configured
            : Path.Combine(AppContext.BaseDirectory, configured);

        Directory.CreateDirectory(_rootPath);
    }

    public string RootPath => _rootPath;

    public async Task<string> SaveAsync(Stream content, string originalFileName, CancellationToken ct = default)
    {
        var extension = Path.GetExtension(originalFileName);
        var storedName = $"{Guid.NewGuid():N}{extension}";
        var fullPath = Path.Combine(_rootPath, storedName);

        await using var fileStream = File.Create(fullPath);
        await content.CopyToAsync(fileStream, ct);

        return storedName;
    }

    public void Delete(string storedFileName)
    {
        var fullPath = Path.Combine(_rootPath, storedFileName);
        if (File.Exists(fullPath))
            File.Delete(fullPath);
    }
}
