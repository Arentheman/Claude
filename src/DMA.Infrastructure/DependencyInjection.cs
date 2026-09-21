using DMA.Application.Common.Interfaces;
using DMA.Infrastructure.Data;
using DMA.Infrastructure.ExternalReference;
using DMA.Infrastructure.Files;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace DMA.Infrastructure;

public static class DependencyInjection
{
    /// <summary>
    /// Registers the EF Core context. Reads "Database:Provider" (Sqlite | Postgres, default Sqlite)
    /// and "ConnectionStrings:Default" so switching to a hosted PostgreSQL later is a config change,
    /// not a code change.
    /// </summary>
    public static IServiceCollection AddInfrastructure(this IServiceCollection services, IConfiguration configuration)
    {
        var provider = configuration["Database:Provider"] ?? "Sqlite";
        var connectionString = configuration.GetConnectionString("Default")
            ?? "Data Source=dungeonmaster.db";

        services.AddDbContext<AppDbContext>(options =>
        {
            switch (provider)
            {
                case "Postgres":
                    options.UseNpgsql(connectionString);
                    break;
                default:
                    options.UseSqlite(connectionString);
                    break;
            }
        });

        services.AddScoped<IApplicationDbContext>(sp => sp.GetRequiredService<AppDbContext>());

        services.AddSingleton<FileStorageService>();
        services.AddSingleton<IFileStorageService>(sp => sp.GetRequiredService<FileStorageService>());

        services.AddHttpClient<ISrdReferenceService, Open5eReferenceService>(client =>
        {
            client.BaseAddress = new Uri("https://api.open5e.com/v1/");
            client.Timeout = TimeSpan.FromSeconds(25);
        });

        return services;
    }
}
