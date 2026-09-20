using Microsoft.EntityFrameworkCore;

namespace DMA.Infrastructure.Data.Seed;

public static class DbInitializer
{
    public static async Task InitializeAsync(AppDbContext db)
    {
        await db.Database.MigrateAsync();

        if (!await db.StatBlocks.AnyAsync())
        {
            db.StatBlocks.AddRange(SrdMonsterSeed.GetMonsters());
            await db.SaveChangesAsync();
        }
    }
}
