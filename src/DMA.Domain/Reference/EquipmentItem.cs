using System.Text.Json;

namespace DMA.Domain.Reference;

public sealed record EquipmentItem(
    string Id,
    string Name,
    string Category,
    string Cost,
    string Weight,
    string Description,
    IReadOnlyDictionary<string, JsonElement> Stats);
