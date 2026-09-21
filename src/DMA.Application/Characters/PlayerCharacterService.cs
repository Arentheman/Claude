using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using DMA.Domain.Enums;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Characters;

public class PlayerCharacterService(IApplicationDbContext db, IFileStorageService fileStorage)
{
    public Task<List<PlayerCharacter>> GetByCampaignAsync(int campaignId, CancellationToken ct = default) =>
        db.PlayerCharacters
            .Include(c => c.Inventory)
            .Where(c => c.CampaignId == campaignId)
            .OrderBy(c => c.Name)
            .ToListAsync(ct);

    public Task<PlayerCharacter?> GetByIdAsync(int id, CancellationToken ct = default) =>
        db.PlayerCharacters
            .Include(c => c.Inventory)
            .Include(c => c.Features)
            .Include(c => c.Attachments)
            .FirstOrDefaultAsync(c => c.Id == id, ct);

    public async Task<PlayerCharacter> CreateAsync(PlayerCharacter character, CancellationToken ct = default)
    {
        ClampBounds(character);
        db.PlayerCharacters.Add(character);
        await db.SaveChangesAsync(ct);
        return character;
    }

    public async Task UpdateAsync(PlayerCharacter character, CancellationToken ct = default)
    {
        ClampBounds(character);
        db.PlayerCharacters.Update(character);
        await db.SaveChangesAsync(ct);
    }

    /// <summary>
    /// Server-side safety net matching the [Range] data annotations on PlayerCharacter: the UI
    /// validates and blocks submission, but this keeps the data sane even for callers that skip it.
    /// </summary>
    private static void ClampBounds(PlayerCharacter character)
    {
        character.Level = Math.Max(1, character.Level);
        character.MaxHp = Math.Max(0, character.MaxHp);
        character.CurrentHp = Math.Max(0, character.CurrentHp);
        character.ArmorClass = Math.Max(0, character.ArmorClass);
        character.Abilities.Clamp();
        character.Currency.Clamp();
    }

    public async Task DeleteAsync(int id, CancellationToken ct = default)
    {
        var character = await db.PlayerCharacters
            .Include(c => c.Attachments)
            .FirstOrDefaultAsync(c => c.Id == id, ct);
        if (character is null) return;

        foreach (var attachment in character.Attachments)
            fileStorage.Delete(attachment.StoredFileName);
        if (character.PortraitPath is not null)
            fileStorage.Delete(character.PortraitPath);

        db.PlayerCharacters.Remove(character);
        await db.SaveChangesAsync(ct);
    }

    public async Task AddInventoryItemAsync(
        int characterId, string name, int quantity, string notes, InventoryItemCategory category, CancellationToken ct = default)
    {
        db.InventoryItems.Add(new InventoryItem
        {
            PlayerCharacterId = characterId,
            Name = name,
            Quantity = Math.Max(0, quantity),
            Notes = notes,
            Category = category
        });
        await db.SaveChangesAsync(ct);
    }

    public async Task UpdateInventoryItemQuantityAsync(int itemId, int quantity, CancellationToken ct = default)
    {
        var item = await db.InventoryItems.FindAsync([itemId], ct);
        if (item is null) return;
        item.Quantity = Math.Max(0, quantity);
        await db.SaveChangesAsync(ct);
    }

    public async Task RemoveInventoryItemAsync(int itemId, CancellationToken ct = default)
    {
        var item = await db.InventoryItems.FindAsync([itemId], ct);
        if (item is null) return;
        db.InventoryItems.Remove(item);
        await db.SaveChangesAsync(ct);
    }

    public async Task AddFeatureAsync(
        int characterId, string name, CharacterFeatureType type, int? level, string description, CancellationToken ct = default)
    {
        db.CharacterFeatures.Add(new CharacterFeature
        {
            PlayerCharacterId = characterId,
            Name = name,
            Type = type,
            Level = type == CharacterFeatureType.Spell ? Math.Clamp(level ?? 0, 0, 9) : null,
            Description = description
        });
        await db.SaveChangesAsync(ct);
    }

    public async Task RemoveFeatureAsync(int featureId, CancellationToken ct = default)
    {
        var feature = await db.CharacterFeatures.FindAsync([featureId], ct);
        if (feature is null) return;
        db.CharacterFeatures.Remove(feature);
        await db.SaveChangesAsync(ct);
    }

    public async Task SetPortraitAsync(int characterId, Stream content, string fileName, CancellationToken ct = default)
    {
        var character = await db.PlayerCharacters.FindAsync([characterId], ct);
        if (character is null) return;

        if (character.PortraitPath is not null)
            fileStorage.Delete(character.PortraitPath);

        character.PortraitPath = await fileStorage.SaveAsync(content, fileName, ct);
        await db.SaveChangesAsync(ct);
    }

    public async Task RemovePortraitAsync(int characterId, CancellationToken ct = default)
    {
        var character = await db.PlayerCharacters.FindAsync([characterId], ct);
        if (character?.PortraitPath is null) return;

        fileStorage.Delete(character.PortraitPath);
        character.PortraitPath = null;
        await db.SaveChangesAsync(ct);
    }

    public async Task AddAttachmentAsync(
        int characterId, Stream content, string originalFileName, string contentType, string caption, CancellationToken ct = default)
    {
        var storedName = await fileStorage.SaveAsync(content, originalFileName, ct);
        db.CharacterAttachments.Add(new CharacterAttachment
        {
            PlayerCharacterId = characterId,
            StoredFileName = storedName,
            OriginalFileName = originalFileName,
            ContentType = contentType,
            Caption = caption
        });
        await db.SaveChangesAsync(ct);
    }

    public async Task RemoveAttachmentAsync(int attachmentId, CancellationToken ct = default)
    {
        var attachment = await db.CharacterAttachments.FindAsync([attachmentId], ct);
        if (attachment is null) return;

        fileStorage.Delete(attachment.StoredFileName);
        db.CharacterAttachments.Remove(attachment);
        await db.SaveChangesAsync(ct);
    }
}
