using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Design;

namespace DMA.Infrastructure.Data;

/// <summary>Used only by `dotnet ef migrations add` at design time; the app itself configures the context via DI.</summary>
public class AppDbContextFactory : IDesignTimeDbContextFactory<AppDbContext>
{
    public AppDbContext CreateDbContext(string[] args)
    {
        var optionsBuilder = new DbContextOptionsBuilder<AppDbContext>();
        optionsBuilder.UseSqlite("Data Source=dungeonmaster.db");
        return new AppDbContext(optionsBuilder.Options);
    }
}
