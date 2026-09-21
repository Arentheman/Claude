using System.Text.Json;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Storage.ValueConversion;

namespace DMA.Infrastructure.Data.Configurations;

/// <summary>Shared EF Core conversion for a List&lt;string&gt; property stored as a JSON column
/// (used for the "active conditions" lists on EncounterParticipant and PlayerCharacter).</summary>
internal static class JsonStringListConversion
{
    public static readonly ValueConverter<List<string>, string> Converter = new(
        v => JsonSerializer.Serialize(v, JsonSerializerOptions.Default),
        v => JsonSerializer.Deserialize<List<string>>(v, JsonSerializerOptions.Default) ?? new());

    public static readonly ValueComparer<List<string>> Comparer = new(
        (a, b) => (a ?? new()).SequenceEqual(b ?? new()),
        v => v.Aggregate(0, (hash, s) => HashCode.Combine(hash, s.GetHashCode())),
        v => v.ToList());
}
