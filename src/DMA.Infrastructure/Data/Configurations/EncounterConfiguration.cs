using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class EncounterConfiguration : IEntityTypeConfiguration<Encounter>
{
    public void Configure(EntityTypeBuilder<Encounter> builder)
    {
        builder.Property(e => e.Name).IsRequired().HasMaxLength(200);

        builder.HasOne(e => e.Session)
            .WithMany()
            .HasForeignKey(e => e.SessionId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasMany(e => e.Participants)
            .WithOne(p => p.Encounter)
            .HasForeignKey(p => p.EncounterId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
