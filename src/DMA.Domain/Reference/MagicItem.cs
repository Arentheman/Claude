namespace DMA.Domain.Reference;

public sealed record MagicItem(
    string Id,
    string Name,
    string Type,
    string Rarity,
    bool RequiresAttunement,
    string? AttunementNote,
    string Description,
    IReadOnlyList<ReferenceTable> Tables);
