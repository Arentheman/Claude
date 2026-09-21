using System.ComponentModel.DataAnnotations;
using DMA.Domain.Enums;

namespace DMA.Domain.Entities;

public class InventoryItem
{
    public int Id { get; set; }
    public int PlayerCharacterId { get; set; }
    public PlayerCharacter PlayerCharacter { get; set; } = null!;

    public string Name { get; set; } = string.Empty;

    [Range(0, int.MaxValue, ErrorMessage = "Количество не может быть отрицательным.")]
    public int Quantity { get; set; } = 1;

    public string Notes { get; set; } = string.Empty;
    public InventoryItemCategory Category { get; set; } = InventoryItemCategory.Equipment;
}
