using DMA.Application.Bestiary;
using DMA.Application.Campaigns;
using DMA.Application.Characters;
using DMA.Application.Encounters;
using DMA.Application.Sessions;
using Microsoft.Extensions.DependencyInjection;

namespace DMA.Application;

public static class DependencyInjection
{
    public static IServiceCollection AddApplication(this IServiceCollection services)
    {
        services.AddScoped<CampaignService>();
        services.AddScoped<SessionService>();
        services.AddScoped<PlayerCharacterService>();
        services.AddScoped<StatBlockService>();
        services.AddScoped<EncounterService>();
        return services;
    }
}
