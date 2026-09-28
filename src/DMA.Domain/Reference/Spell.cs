namespace DMA.Domain.Reference;

public sealed record Spell(
    string Id,
    string Name,
    int Level,
    string School,
    IReadOnlyList<string> Classes,
    string CastingTime,
    string Range,
    string Components,
    string Duration,
    bool Ritual,
    bool Concentration,
    string Description,
    string? AtHigherLevels,
    IReadOnlyList<ReferenceTable> Tables);
