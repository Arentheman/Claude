namespace DMA.Domain.Reference;

public sealed record ReferenceTable(string Title, IReadOnlyList<string> Columns, IReadOnlyList<IReadOnlyList<string>> Rows);

public sealed record RuleSection(
    string Id,
    string Title,
    string? ParentId,
    int Order,
    string Content,
    IReadOnlyList<ReferenceTable> Tables);

/// <summary>
/// A RuleSection plus its children, assembled from the flat RuleSection list by ReferenceDataService
/// so the web layer can render it the same way it renders the Story tree.
/// </summary>
public sealed class RuleSectionNode
{
    public required RuleSection Section { get; init; }
    public IReadOnlyList<RuleSectionNode> Children { get; init; } = [];
}
