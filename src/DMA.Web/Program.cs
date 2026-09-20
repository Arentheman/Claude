using System.Diagnostics;
using DMA.Application;
using DMA.Infrastructure;
using DMA.Infrastructure.Data;
using DMA.Infrastructure.Data.Seed;
using DMA.Infrastructure.Files;
using DMA.Web.Components;
using Microsoft.AspNetCore.Hosting.Server;
using Microsoft.AspNetCore.Hosting.Server.Features;
using Microsoft.Extensions.FileProviders;

var builder = WebApplication.CreateBuilder(args);

// Add services to the container.
builder.Services.AddRazorComponents()
    .AddInteractiveServerComponents();

builder.Services.AddApplication();
builder.Services.AddInfrastructure(builder.Configuration);

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await DbInitializer.InitializeAsync(db);
}

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error", createScopeForErrors: true);
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseHttpsRedirection();

app.UseStaticFiles();

var fileStorage = app.Services.GetRequiredService<FileStorageService>();
app.UseStaticFiles(new StaticFileOptions
{
    FileProvider = new PhysicalFileProvider(fileStorage.RootPath),
    RequestPath = "/uploads"
});

app.UseAntiforgery();

app.MapRazorComponents<App>()
    .AddInteractiveServerRenderMode();

if (app.Configuration.GetValue("App:OpenBrowserOnStart", true))
{
    app.Lifetime.ApplicationStarted.Register(() =>
    {
        var address = app.Services.GetRequiredService<IServer>()
            .Features.Get<IServerAddressesFeature>()?
            .Addresses.FirstOrDefault();

        if (address is null) return;

        try
        {
            Process.Start(new ProcessStartInfo(address) { UseShellExecute = true });
        }
        catch
        {
            // Best-effort convenience for the packaged desktop-style build; ignore if it fails
            // (e.g. no default browser registered) — the console still prints the address.
        }
    });
}

app.Run();
