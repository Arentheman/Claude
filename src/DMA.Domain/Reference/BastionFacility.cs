namespace DMA.Domain.Reference;

public sealed record BastionFacility(
    string Id,
    string Name,
    string Kind,
    int? Level,
    string? Requirements,
    string? Size,
    string? Hirelings,
    IReadOnlyList<string> Orders,
    string Description,
    IReadOnlyList<string> Benefits);
