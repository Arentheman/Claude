namespace DMA.Domain.Entities;

/// <summary>A screenshot or image attached to a player character (item art, a map, a portrait reference, etc).</summary>
public class CharacterAttachment
{
    public int Id { get; set; }
    public int PlayerCharacterId { get; set; }
    public PlayerCharacter PlayerCharacter { get; set; } = null!;

    /// <summary>Name of the file on disk (see IFileStorageService), not the original upload name.</summary>
    public string StoredFileName { get; set; } = string.Empty;
    public string OriginalFileName { get; set; } = string.Empty;
    public string ContentType { get; set; } = string.Empty;
    public string Caption { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
