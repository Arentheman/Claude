namespace DMA.Domain.Reference;

public sealed record SpeciesTrait(string Name, string Description);

public sealed record Species(
    string Id,
    string Name,
    string CreatureType,
    string Size,
    string Speed,
    string Description,
    IReadOnlyList<SpeciesTrait> Traits,
    IReadOnlyList<ReferenceTable> Tables);
