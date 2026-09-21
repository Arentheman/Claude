using System.Net.Http.Json;
using System.Text;
using DMA.Application.Common.Interfaces;
using DMA.Application.Reference;

namespace DMA.Infrastructure.ExternalReference;

/// <summary>
/// Looks up spells and monsters from open5e.com's public API, which serves the D&amp;D 5e SRD
/// (open, OGL-licensed content) — not the copyrighted Player's Handbook or Monster Manual.
/// </summary>
public class Open5eReferenceService(HttpClient http) : ISrdReferenceService
{
    public async Task<IReadOnlyList<SrdSpellSummary>> SearchSpellsAsync(string query, CancellationToken ct = default)
    {
        var url = $"spells/?search={Uri.EscapeDataString(query)}&limit=20";
        var response = await http.GetFromJsonAsync<Open5eListResponse<Open5eSpell>>(url, ct)
            ?? new Open5eListResponse<Open5eSpell>();

        return response.Results.Select(s => new SrdSpellSummary(
            Name: s.Name,
            Level: string.IsNullOrEmpty(s.Level) ? "Заговор" : s.Level,
            School: s.School,
            CastingTime: s.CastingTime,
            Range: s.Range,
            Components: s.Components,
            Duration: s.Duration,
            Concentration: s.Concentration.Equals("yes", StringComparison.OrdinalIgnoreCase),
            Ritual: s.Ritual.Equals("yes", StringComparison.OrdinalIgnoreCase),
            Classes: s.DndClass,
            Description: s.Desc)).ToList();
    }

    public async Task<IReadOnlyList<SrdMonsterSummary>> SearchMonstersAsync(string query, CancellationToken ct = default)
    {
        var url = $"monsters/?search={Uri.EscapeDataString(query)}&limit=20";
        var response = await http.GetFromJsonAsync<Open5eListResponse<Open5eMonster>>(url, ct)
            ?? new Open5eListResponse<Open5eMonster>();

        return response.Results.Select(m => new SrdMonsterSummary(
            Name: m.Name,
            Size: m.Size,
            Type: m.Type,
            Alignment: m.Alignment,
            ChallengeRating: m.ChallengeRating,
            ArmorClass: m.ArmorClass,
            HitPoints: m.HitPoints,
            Speed: FormatSpeed(m.Speed),
            Description: BuildDescription(m))).ToList();
    }

    private static string FormatSpeed(Dictionary<string, object>? speed)
    {
        if (speed is null || speed.Count == 0) return "";
        return string.Join(", ", speed.Select(kv => $"{kv.Key} {kv.Value} ft."));
    }

    private static string BuildDescription(Open5eMonster monster)
    {
        var sb = new StringBuilder();

        if (!string.IsNullOrWhiteSpace(monster.Desc))
            sb.AppendLine(monster.Desc);

        foreach (var entry in monster.SpecialAbilities ?? [])
            sb.AppendLine($"{entry.Name}: {entry.Desc}");

        foreach (var entry in monster.Actions ?? [])
            sb.AppendLine($"{entry.Name}: {entry.Desc}");

        return sb.ToString().Trim();
    }
}
