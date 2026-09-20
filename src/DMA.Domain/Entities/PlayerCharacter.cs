namespace DMA.Domain.Entities;

public class PlayerCharacter
{
    public int Id { get; set; }
    public int CampaignId { get; set; }
    public Campaign Campaign { get; set; } = null!;

    public string Name { get; set; } = string.Empty;
    public string PlayerName { get; set; } = string.Empty;
    public string Race { get; set; } = string.Empty;
    public string Class { get; set; } = string.Empty;
    public int Level { get; set; } = 1;

    public int MaxHp { get; set; }
    public int CurrentHp { get; set; }
    public int ArmorClass { get; set; }

    public AbilityScores Abilities { get; set; } = new();

    public string Notes { get; set; } = string.Empty;

    public List<InventoryItem> Inventory { get; set; } = new();
}
