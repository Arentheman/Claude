using DMA.Domain.Reference;

namespace DMA.Application.Common.Interfaces;

/// <summary>
/// Serves the bundled, read-only reference-book content (rules, feats, equipment, and later
/// bastions/magic items/classes) — loaded once from embedded JSON at startup. Not backed by the
/// database: this data ships with the app and isn't user-editable.
/// </summary>
public interface IReferenceDataService
{
    IReadOnlyList<RuleSectionNode> GetRuleTree();
    RuleSection? GetRuleSection(string id);
    IReadOnlyList<RuleSection> SearchRules(string query);

    IReadOnlyList<Feat> GetFeats();
    IReadOnlyList<Feat> SearchFeats(string query);

    IReadOnlyList<EquipmentItem> GetEquipment();
    IReadOnlyList<EquipmentItem> SearchEquipment(string query);
}
