using System.Text.Json.Serialization;

namespace DMA.Infrastructure.ExternalReference;

/// <summary>Raw JSON shape of the open5e.com v1 API (SRD-licensed content). Internal —
/// the Application layer only ever sees the mapped SrdSpellSummary/SrdMonsterSummary records.</summary>
internal class Open5eListResponse<T>
{
    [JsonPropertyName("count")]
    public int Count { get; set; }

    [JsonPropertyName("results")]
    public List<T> Results { get; set; } = [];
}

internal class Open5eSpell
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("desc")]
    public string Desc { get; set; } = string.Empty;

    [JsonPropertyName("range")]
    public string Range { get; set; } = string.Empty;

    [JsonPropertyName("components")]
    public string Components { get; set; } = string.Empty;

    [JsonPropertyName("duration")]
    public string Duration { get; set; } = string.Empty;

    [JsonPropertyName("concentration")]
    public string Concentration { get; set; } = string.Empty;

    [JsonPropertyName("casting_time")]
    public string CastingTime { get; set; } = string.Empty;

    [JsonPropertyName("level")]
    public string Level { get; set; } = string.Empty;

    [JsonPropertyName("school")]
    public string School { get; set; } = string.Empty;

    [JsonPropertyName("ritual")]
    public string Ritual { get; set; } = string.Empty;

    [JsonPropertyName("dnd_class")]
    public string DndClass { get; set; } = string.Empty;
}

internal class Open5eMonster
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("size")]
    public string Size { get; set; } = string.Empty;

    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("alignment")]
    public string Alignment { get; set; } = string.Empty;

    [JsonPropertyName("challenge_rating")]
    public string ChallengeRating { get; set; } = string.Empty;

    [JsonPropertyName("armor_class")]
    public int ArmorClass { get; set; }

    [JsonPropertyName("hit_points")]
    public int HitPoints { get; set; }

    [JsonPropertyName("speed")]
    public Dictionary<string, object>? Speed { get; set; }

    [JsonPropertyName("desc")]
    public string? Desc { get; set; }

    [JsonPropertyName("actions")]
    public List<Open5eNamedEntry>? Actions { get; set; }

    [JsonPropertyName("special_abilities")]
    public List<Open5eNamedEntry>? SpecialAbilities { get; set; }
}

internal class Open5eNamedEntry
{
    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("desc")]
    public string Desc { get; set; } = string.Empty;
}
