using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class CharacterFeatureConfiguration : IEntityTypeConfiguration<CharacterFeature>
{
    public void Configure(EntityTypeBuilder<CharacterFeature> builder)
    {
        builder.Property(f => f.Name).IsRequired().HasMaxLength(200);
        builder.Property(f => f.Description).HasMaxLength(4000);
    }
}
