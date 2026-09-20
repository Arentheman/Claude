using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using DMA.Domain.Enums;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Bestiary;

public class StatBlockService(IApplicationDbContext db)
{
    public Task<List<StatBlock>> GetAllAsync(StatBlockType? type = null, CancellationToken ct = default)
    {
        var query = db.StatBlocks.AsQueryable();
        if (type is not null)
            query = query.Where(s => s.Type == type);
        return query.OrderBy(s => s.Name).ToListAsync(ct);
    }

    public Task<StatBlock?> GetByIdAsync(int id, CancellationToken ct = default) =>
        db.StatBlocks.FirstOrDefaultAsync(s => s.Id == id, ct);

    public async Task<StatBlock> CreateAsync(StatBlock statBlock, CancellationToken ct = default)
    {
        db.StatBlocks.Add(statBlock);
        await db.SaveChangesAsync(ct);
        return statBlock;
    }

    public async Task UpdateAsync(StatBlock statBlock, CancellationToken ct = default)
    {
        db.StatBlocks.Update(statBlock);
        await db.SaveChangesAsync(ct);
    }

    public async Task DeleteAsync(int id, CancellationToken ct = default)
    {
        var statBlock = await db.StatBlocks.FindAsync([id], ct);
        if (statBlock is null) return;
        db.StatBlocks.Remove(statBlock);
        await db.SaveChangesAsync(ct);
    }
}
