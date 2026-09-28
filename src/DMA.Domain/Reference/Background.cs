namespace DMA.Domain.Reference;

public sealed record Background(
    string Id,
    string Name,
    IReadOnlyList<string> AbilityScores,
    string Feat,
    IReadOnlyList<string> SkillProficiencies,
    string ToolProficiency,
    string Equipment);
