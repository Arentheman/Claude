using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class EncounterParticipantConfiguration : IEntityTypeConfiguration<EncounterParticipant>
{
    public void Configure(EntityTypeBuilder<EncounterParticipant> builder)
    {
        builder.Property(p => p.Name).IsRequired().HasMaxLength(200);

        builder.Property(p => p.Conditions)
            .HasConversion(JsonStringListConversion.Converter)
            .Metadata.SetValueComparer(JsonStringListConversion.Comparer);
    }
}
