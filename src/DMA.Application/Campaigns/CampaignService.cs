using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Campaigns;

public class CampaignService(IApplicationDbContext db)
{
    public Task<List<Campaign>> GetAllAsync(CancellationToken ct = default) =>
        db.Campaigns.OrderByDescending(c => c.CreatedAt).ToListAsync(ct);

    public Task<Campaign?> GetByIdAsync(int id, CancellationToken ct = default) =>
        db.Campaigns.FirstOrDefaultAsync(c => c.Id == id, ct);

    public async Task<Campaign> CreateAsync(string name, string description, CancellationToken ct = default)
    {
        var campaign = new Campaign { Name = name, Description = description };
        db.Campaigns.Add(campaign);
        await db.SaveChangesAsync(ct);
        return campaign;
    }

    public async Task UpdateAsync(Campaign campaign, CancellationToken ct = default)
    {
        db.Campaigns.Update(campaign);
        await db.SaveChangesAsync(ct);
    }

    public async Task DeleteAsync(int id, CancellationToken ct = default)
    {
        var campaign = await db.Campaigns.FindAsync([id], ct);
        if (campaign is null) return;
        db.Campaigns.Remove(campaign);
        await db.SaveChangesAsync(ct);
    }
}
