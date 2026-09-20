using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Sessions;

public class SessionService(IApplicationDbContext db)
{
    public Task<List<Session>> GetByCampaignAsync(int campaignId, CancellationToken ct = default) =>
        db.Sessions.Where(s => s.CampaignId == campaignId)
            .OrderByDescending(s => s.Number)
            .ToListAsync(ct);

    public Task<Session?> GetByIdAsync(int id, CancellationToken ct = default) =>
        db.Sessions.FirstOrDefaultAsync(s => s.Id == id, ct);

    public async Task<Session> CreateAsync(int campaignId, string title, CancellationToken ct = default)
    {
        var nextNumber = await db.Sessions
            .Where(s => s.CampaignId == campaignId)
            .Select(s => (int?)s.Number)
            .MaxAsync(ct) ?? 0;

        var session = new Session
        {
            CampaignId = campaignId,
            Title = title,
            Number = nextNumber + 1
        };
        db.Sessions.Add(session);
        await db.SaveChangesAsync(ct);
        return session;
    }

    public async Task UpdateAsync(Session session, CancellationToken ct = default)
    {
        db.Sessions.Update(session);
        await db.SaveChangesAsync(ct);
    }

    public async Task DeleteAsync(int id, CancellationToken ct = default)
    {
        var session = await db.Sessions.FindAsync([id], ct);
        if (session is null) return;
        db.Sessions.Remove(session);
        await db.SaveChangesAsync(ct);
    }
}
