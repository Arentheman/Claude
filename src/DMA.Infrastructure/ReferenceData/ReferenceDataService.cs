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
    private readonly IReadOnlyList<CharacterClass> _classes;
    private readonly IReadOnlyList<Species> _species;
    private readonly IReadOnlyList<Background> _backgrounds;
    private readonly IReadOnlyList<RuleSection> _spellRuleSections;
    private readonly IReadOnlyList<RuleSectionNode> _spellRuleTree;
    private readonly IReadOnlyList<Spell> _spells;

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

        _classes = LoadEmbedded<CharacterClassDto>("classes.json")
            .Select(d => new CharacterClass(d.Id, d.Name, d.HitDie, d.PrimaryAbilities, d.SavingThrows,
                d.ArmorProficiencies, d.WeaponProficiencies, d.ToolProficiencies, d.SkillProficiencies,
                d.StartingEquipment, ToReferenceTables(d.Tables),
                (d.Features ?? []).Select(f => new ClassFeature(f.Level, f.Name, f.Description)).ToList(),
                (d.Subclasses ?? []).Select(s => new Subclass(s.Id, s.Name, s.UnlockLevel, s.Description,
                    (s.Features ?? []).Select(f => new ClassFeature(f.Level, f.Name, f.Description)).ToList(),
                    ToReferenceTables(s.Tables))).ToList(),
                d.Multiclassing))
            .ToList();

        _species = LoadEmbedded<SpeciesDto>("species.json")
            .Select(d => new Species(d.Id, d.Name, d.CreatureType, d.Size, d.Speed, d.Description,
                (d.Traits ?? []).Select(t => new SpeciesTrait(t.Name, t.Description)).ToList(),
                ToReferenceTables(d.Tables)))
            .ToList();

        _backgrounds = LoadEmbedded<BackgroundDto>("backgrounds.json")
            .Select(d => new Background(d.Id, d.Name, d.AbilityScores, d.Feat, d.SkillProficiencies,
                d.ToolProficiency, d.Equipment))
            .ToList();

        _spellRuleSections = LoadRuleSections("spell-rules.json");
        _spellRuleTree = BuildRuleTree(_spellRuleSections);

        _spells = LoadEmbedded<SpellDto>("spells.json")
            .Select(d => new Spell(d.Id, d.Name, d.Level, d.School, d.Classes, d.CastingTime, d.Range,
                d.Components, d.Duration, d.Ritual, d.Concentration, d.Description, d.AtHigherLevels,
                ToReferenceTables(d.Tables)))
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

    public IReadOnlyList<CharacterClass> GetClasses() => _classes;

    public CharacterClass? GetClass(string id) => _classes.FirstOrDefault(c => c.Id == id);

    public IReadOnlyList<Species> GetSpecies() => _species;

    public IReadOnlyList<Background> GetBackgrounds() => _backgrounds;

    public IReadOnlyList<RuleSectionNode> GetSpellRuleTree() => _spellRuleTree;

    public RuleSection? GetSpellRuleSection(string id) => _spellRuleSections.FirstOrDefault(s => s.Id == id);

    public IReadOnlyList<RuleSection> SearchSpellRules(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return [];
        return _spellRuleSections
            .Where(s => Matches(s.Title, query) || Matches(s.Content, query))
            .ToList();
    }

    public IReadOnlyList<Spell> GetSpells() => _spells;

    public IReadOnlyList<Spell> SearchSpells(string query)
    {
        if (string.IsNullOrWhiteSpace(query)) return _spells;
        return _spells
            .Where(s => Matches(s.Name, query) || Matches(s.Description, query))
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

        [JsonConverter(typeof(StringMatrixConverter))]
        public List<List<string>> Rows { get; set; } = [];
    }

    /// <summary>
    /// Table cells should be strings, but the extraction agents that produced this bundled data
    /// occasionally emitted a bare JSON number for a numeric-looking cell (e.g. a spell-slot count)
    /// instead of a quoted string. Tolerate any JSON primitive here rather than failing to load the
    /// whole file over one mistyped cell.
    /// </summary>
    private sealed class StringMatrixConverter : JsonConverter<List<List<string>>>
    {
        public override List<List<string>> Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
        {
            var rows = new List<List<string>>();
            if (reader.TokenType != JsonTokenType.StartArray) return rows;
            while (reader.Read() && reader.TokenType != JsonTokenType.EndArray)
            {
                var row = new List<string>();
                while (reader.Read() && reader.TokenType != JsonTokenType.EndArray)
                {
                    row.Add(reader.TokenType switch
                    {
                        JsonTokenType.String => reader.GetString() ?? "",
                        JsonTokenType.Number => reader.GetDouble().ToString(System.Globalization.CultureInfo.InvariantCulture),
                        JsonTokenType.True => "true",
                        JsonTokenType.False => "false",
                        JsonTokenType.Null => "",
                        _ => ""
                    });
                }
                rows.Add(row);
            }
            return rows;
        }

        public override void Write(Utf8JsonWriter writer, List<List<string>> value, JsonSerializerOptions options) =>
            JsonSerializer.Serialize(writer, value, options);
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

    private sealed class ClassFeatureDto
    {
        public int Level { get; set; }
        public string Name { get; set; } = "";
        public string Description { get; set; } = "";
    }

    private sealed class SubclassDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public int UnlockLevel { get; set; }
        public string Description { get; set; } = "";
        public List<ClassFeatureDto>? Features { get; set; }
        public List<TableDto>? Tables { get; set; }
    }

    private sealed class CharacterClassDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string HitDie { get; set; } = "";
        public List<string> PrimaryAbilities { get; set; } = [];
        public List<string> SavingThrows { get; set; } = [];
        public List<string> ArmorProficiencies { get; set; } = [];
        public List<string> WeaponProficiencies { get; set; } = [];
        public List<string> ToolProficiencies { get; set; } = [];
        public string SkillProficiencies { get; set; } = "";
        public string StartingEquipment { get; set; } = "";
        public List<TableDto>? Tables { get; set; }
        public List<ClassFeatureDto>? Features { get; set; }
        public List<SubclassDto>? Subclasses { get; set; }
        public string Multiclassing { get; set; } = "";
    }

    private sealed class SpeciesTraitDto
    {
        public string Name { get; set; } = "";
        public string Description { get; set; } = "";
    }

    private sealed class SpeciesDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public string CreatureType { get; set; } = "";
        public string Size { get; set; } = "";
        public string Speed { get; set; } = "";
        public string Description { get; set; } = "";
        public List<SpeciesTraitDto>? Traits { get; set; }
        public List<TableDto>? Tables { get; set; }
    }

    private sealed class BackgroundDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public List<string> AbilityScores { get; set; } = [];
        public string Feat { get; set; } = "";
        public List<string> SkillProficiencies { get; set; } = [];
        public string ToolProficiency { get; set; } = "";
        public string Equipment { get; set; } = "";
    }

    private sealed class SpellDto
    {
        public string Id { get; set; } = "";
        public string Name { get; set; } = "";
        public int Level { get; set; }
        public string School { get; set; } = "";
        public List<string> Classes { get; set; } = [];
        public string CastingTime { get; set; } = "";
        public string Range { get; set; } = "";
        public string Components { get; set; } = "";
        public string Duration { get; set; } = "";
        public bool Ritual { get; set; }
        public bool Concentration { get; set; }
        public string Description { get; set; } = "";
        public string? AtHigherLevels { get; set; }
        public List<TableDto>? Tables { get; set; }
    }
}
