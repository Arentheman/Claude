using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Characters;

public class PlayerCharacterService(IApplicationDbContext db)
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
            .FirstOrDefaultAsync(c => c.Id == id, ct);

    public async Task<PlayerCharacter> CreateAsync(PlayerCharacter character, CancellationToken ct = default)
    {
        db.PlayerCharacters.Add(character);
        await db.SaveChangesAsync(ct);
        return character;
    }

    public async Task UpdateAsync(PlayerCharacter character, CancellationToken ct = default)
    {
        db.PlayerCharacters.Update(character);
        await db.SaveChangesAsync(ct);
    }

    public async Task DeleteAsync(int id, CancellationToken ct = default)
    {
        var character = await db.PlayerCharacters.FindAsync([id], ct);
        if (character is null) return;
        db.PlayerCharacters.Remove(character);
        await db.SaveChangesAsync(ct);
    }

    public async Task AddInventoryItemAsync(int characterId, string name, int quantity, string notes, CancellationToken ct = default)
    {
        db.InventoryItems.Add(new InventoryItem
        {
            PlayerCharacterId = characterId,
            Name = name,
            Quantity = quantity,
            Notes = notes
        });
        await db.SaveChangesAsync(ct);
    }

    public async Task RemoveInventoryItemAsync(int itemId, CancellationToken ct = default)
    {
        var item = await db.InventoryItems.FindAsync([itemId], ct);
        if (item is null) return;
        db.InventoryItems.Remove(item);
        await db.SaveChangesAsync(ct);
    }
}
