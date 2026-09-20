using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class StatBlockConfiguration : IEntityTypeConfiguration<StatBlock>
{
    public void Configure(EntityTypeBuilder<StatBlock> builder)
    {
        builder.Property(s => s.Name).IsRequired().HasMaxLength(200);
        builder.Property(s => s.ChallengeRating).HasMaxLength(20);
        builder.Property(s => s.Speed).HasMaxLength(100);
        builder.Property(s => s.Description).HasMaxLength(4000);
        builder.Property(s => s.Source).HasMaxLength(100);

        builder.OwnsOne(s => s.Abilities, ab =>
        {
            ab.Property(a => a.Strength).HasColumnName("Str");
            ab.Property(a => a.Dexterity).HasColumnName("Dex");
            ab.Property(a => a.Constitution).HasColumnName("Con");
            ab.Property(a => a.Intelligence).HasColumnName("Int");
            ab.Property(a => a.Wisdom).HasColumnName("Wis");
            ab.Property(a => a.Charisma).HasColumnName("Cha");
        });
    }
}
