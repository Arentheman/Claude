namespace DMA.Domain.Reference;

public sealed record ClassFeature(int Level, string Name, string Description);

public sealed record Subclass(
    string Id,
    string Name,
    int UnlockLevel,
    string Description,
    IReadOnlyList<ClassFeature> Features,
    IReadOnlyList<ReferenceTable> Tables);

public sealed record CharacterClass(
    string Id,
    string Name,
    string HitDie,
    IReadOnlyList<string> PrimaryAbilities,
    IReadOnlyList<string> SavingThrows,
    IReadOnlyList<string> ArmorProficiencies,
    IReadOnlyList<string> WeaponProficiencies,
    IReadOnlyList<string> ToolProficiencies,
    string SkillProficiencies,
    string StartingEquipment,
    IReadOnlyList<ReferenceTable> Tables,
    IReadOnlyList<ClassFeature> Features,
    IReadOnlyList<Subclass> Subclasses,
    string Multiclassing);
