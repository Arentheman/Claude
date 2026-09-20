using System.Text.Json;
using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.ChangeTracking;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class EncounterParticipantConfiguration : IEntityTypeConfiguration<EncounterParticipant>
{
    public void Configure(EntityTypeBuilder<EncounterParticipant> builder)
    {
        builder.Property(p => p.Name).IsRequired().HasMaxLength(200);

        var conditionsComparer = new ValueComparer<List<string>>(
            (a, b) => (a ?? new()).SequenceEqual(b ?? new()),
            v => v.Aggregate(0, (hash, s) => HashCode.Combine(hash, s.GetHashCode())),
            v => v.ToList());

        builder.Property(p => p.Conditions)
            .HasConversion(
                v => JsonSerializer.Serialize(v, JsonSerializerOptions.Default),
                v => JsonSerializer.Deserialize<List<string>>(v, JsonSerializerOptions.Default) ?? new())
            .Metadata.SetValueComparer(conditionsComparer);
    }
}
