using System.Reflection;
using System.Text.Json;
using System.Text.Json.Serialization;
using DMA.Application.Common.Interfaces;
using DMA.Domain.Reference;

namespace DMA.Infrastructure.ReferenceData;

/// <summary>
/// Loads the bundled reference-book JSON (embedded resources, see DMA.Infrastructure.csproj) once
/// at construction and serves it from memory. Registered as a singleton — the data is fixed and
/// never changes at runtime.
/// </summary>
public sealed class ReferenceDataService : IReferenceDataService
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    private readonly IReadOnlyList<RuleSection> _ruleSections;
    private readonly IReadOnlyList<RuleSectionNode> _ruleTree;
    private readonly IReadOnlyList<Feat> _feats;
    private readonly IReadOnlyList<EquipmentItem> _equipment;
    private readonly IReadOnlyList<RuleSection> _bastionRuleSections;
    private readonly IReadOnlyList<RuleSectionNode> _bastionRuleTree;
    private readonly IReadOnlyList<BastionFacility> _bastionFacilities;
    private readonly IReadOnlyList<RuleSection> _magicItemRuleSections;
    private readonly IReadOnlyList<RuleSectionNode> _magicItemRuleTree;
    private readonly IReadOnlyList<MagicItem> _magicItems;

    public ReferenceDataService()
    {
        _ruleSections = LoadRuleSections("rule-sections.json");
        _ruleTree = BuildRuleTree(_ruleSections);

        _feats = LoadEmbedded<FeatDto>("feats.json")
            .Select(d => new Feat(d.Id, d.Name, d.Category, d.Prerequisite, d.Repeatable, d.Summary, d.Benefits))
            .ToList();

        _equipment = LoadEmbedded<EquipmentItemDto>("equipment.json")
            .Select(d => new EquipmentItem(d.Id, d.Name, d.Category, d.Cost, d.Weight, d.Description,
                d.Stats ?? new Dictionary<string, JsonElement>()))
            .ToList();

        _bastionRuleSections = LoadRuleSections("bastion-rules.json");
        _bastionRuleTree = BuildRuleTree(_bastionRuleSections);

        _bastionFacilities = LoadEmbedded<BastionFacilityDto>("bastion-facilities.json")
            .Select(d => new BastionFacility(d.Id, d.Name, d.Kind, d.Level, d.Requirements, d.Size,
                d.Hirelings, d.Orders, d.Description, d.Benefits))
            .ToList();

        _magicItemRuleSections = LoadRuleSections("magic-item-rules.json");
        _magicItemRuleTree = BuildRuleTree(_magicItemRuleSections);

        _magicItems = LoadEmbedded<MagicItemDto>("magic-items.json")
            .Select(d => new MagicItem(d.Id, d.Name, d.Type, d.Rarity, d.RequiresAttunement,
                d.AttunementNote, d.Description, ToReferenceTables(d.Tables)))
            .ToList();
    }

    private static List<RuleSection> LoadRuleSections(string fileName) =>
        LoadEmbedded<RuleSectionDto>(fileName)
            .Select(d => new RuleSection(d.Id, d.Title, d.ParentId, d.Order, d.Content, ToReferenceTables(d.Tables)))
            .ToList();

    private static List<ReferenceTable> ToReferenceTables(List<TableDto>? tables) =>
        (tables ?? [])
            .Select(t => new ReferenceTable(t.Title, t.Columns, t.Rows))
            .ToList();

    public IReadOnlyList<RuleSectionNode> GetRuleTree() => _ruleTree;

    public RuleSection? GetRuleSection(string id) => _ruleSections.FirstOrDefault(s => s.Id == id);

    public IReadOnlyList<RuleSection> SearchRules(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return [];
        return _ruleSections
            .Where(s => Matches(s.Title, query) || Matches(s.Content, query))
            .ToList();
    }

    public IReadOnlyList<Feat> GetFeats() => _feats;

    public IReadOnlyList<Feat> SearchFeats(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return _feats;
        return _feats
            .Where(f => Matches(f.Name, query) || Matches(f.Summary, query) || f.Benefits.Any(b => Matches(b, query)))
            .ToList();
    }

    public IReadOnlyList<EquipmentItem> GetEquipment() => _equipment;

    public IReadOnlyList<EquipmentItem> SearchEquipment(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return _equipment;
        return _equipment
            .Where(e => Matches(e.Name, query) || Matches(e.Description, query))
            .ToList();
    }

    public IReadOnlyList<RuleSectionNode> GetBastionRuleTree() => _bastionRuleTree;

    public RuleSection? GetBastionRuleSection(string id) => _bastionRuleSections.FirstOrDefault(s => s.Id == id);

    public IReadOnlyList<RuleSection> SearchBastionRules(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return [];
        return _bastionRuleSections
            .Where(s => Matches(s.Title, query) || Matches(s.Content, query))
            .ToList();
    }

    public IReadOnlyList<BastionFacility> GetBastionFacilities() => _bastionFacilities;

    public IReadOnlyList<BastionFacility> SearchBastionFacilities(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return _bastionFacilities;
        return _bastionFacilities
            .Where(f => Matches(f.Name, query) || Matches(f.Description, query) || f.Benefits.Any(b => Matches(b, query)))
            .ToList();
    }

    public IReadOnlyList<RuleSectionNode> GetMagicItemRuleTree() => _magicItemRuleTree;

    public RuleSection? GetMagicItemRuleSection(string id) => _magicItemRuleSections.FirstOrDefault(s => s.Id == id);

    public IReadOnlyList<RuleSection> SearchMagicItemRules(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return [];
        return _magicItemRuleSections
            .Where(s => Matches(s.Title, query) || Matches(s.Content, query))
            .ToList();
    }

    public IReadOnlyList<MagicItem> GetMagicItems() => _magicItems;

    public IReadOnlyList<MagicItem> SearchMagicItems(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return _magicItems;
        return _magicItems
            .Where(m => Matches(m.Name, query) || Matches(m.Description, query))
            .ToList();
    }

    private static bool Matches(string haystack, string query) =>
        haystack.Contains(query, StringComparison.InvariantCultureIgnoreCase);

    private static IReadOnlyList<RuleSectionNode> BuildRuleTree(IReadOnlyList<RuleSection> sections)
    {
        var byParent = sections
            .OrderBy(s => s.Order)
            .GroupBy(s => s.ParentId ?? "")
            .ToDictionary(g => g.Key, g => g.ToList());

        List<RuleSectionNode> Build(string parentKey) =>
            byParent.TryGetValue(parentKey, out var children)
                ? children.Select(s => new RuleSectionNode { Section = s, Children = Build(s.Id) }).ToList()
                : [];

        return Build("");
    }

    private static List<T> LoadEmbedded<T>(string fileName)
    {
        var assembly = Assembly.GetExecutingAssembly();
        var resourceName = assembly.GetManifestResourceNames()
            .FirstOrDefault(n => n.EndsWith("." + fileName, StringComparison.Ordinal))
            ?? throw new InvalidOperationException($"Embedded reference data resource not found: {fileName}");

        using var stream = assembly.GetManifestResourceStream(resourceName)
            ?? throw new InvalidOperationException($"Could not open embedded resource stream: {resourceName}");

        return JsonSerializer.Deserialize<List<T>>(stream, JsonOptions)
            ?? throw new InvalidOperationException($"Failed to deserialize reference data: {fileName}");
    }

    private sealed class TableDto
    {
        public string Title { get; set; } = "";
        public List<string> Columns { get; set; } = [];
        public List<List<string>> Rows { get; set; } = [];
    }

    private sealed class RuleSectionDto
    {
        public string Id { get; set; } = "";
        public string Title { get; set; } = "";
        public string? ParentId { get; set; }
        public int Order { get; set; }
        public string Content { get; set; } = "";
        public List<TableDto>? Tables { get; set; }
    }

    private sealed class FeatDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string Category { get; set; } = "";
        public string? Prerequisite { get; set; }
        public bool Repeatable { get; set; }
        public string Summary { get; set; } = "";
        public List<string> Benefits { get; set; } = [];
    }

    private sealed class EquipmentItemDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string Category { get; set; } = "";
        public string Cost { get; set; } = "";
        public string Weight { get; set; } = "";
        public string Description { get; set; } = "";
        public Dictionary<string, JsonElement>? Stats { get; set; }
    }

    private sealed class BastionFacilityDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string Kind { get; set; } = "";
        public int? Level { get; set; }
        public string? Requirements { get; set; }
        public string? Size { get; set; }
        public string? Hirelings { get; set; }
        public List<string> Orders { get; set; } = [];
        public string Description { get; set; } = "";
        public List<string> Benefits { get; set; } = [];
    }

    private sealed class MagicItemDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string Type { get; set; } = "";
        public string Rarity { get; set; } = "";
        public bool RequiresAttunement { get; set; }
        public string? AttunementNote { get; set; }
        public string Description { get; set; } = "";
        public List<TableDto>? Tables { get; set; }
    }
}
