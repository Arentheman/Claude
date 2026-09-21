namespace DMA.Application.Reference;

public record SrdSpellSummary(
    string Name,
    string Level,
    string School,
    string CastingTime,
    string Range,
    string Components,
    string Duration,
    bool Concentration,
    bool Ritual,
    string Classes,
    string Description);
