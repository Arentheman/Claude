namespace DMA.Domain.Reference;

public sealed record Feat(
    string Id,
    string Name,
    string Category,
    string? Prerequisite,
    bool Repeatable,
    string Summary,
    IReadOnlyList<string> Benefits);
