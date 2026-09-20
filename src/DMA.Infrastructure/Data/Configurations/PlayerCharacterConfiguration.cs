using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class PlayerCharacterConfiguration : IEntityTypeConfiguration<PlayerCharacter>
{
    public void Configure(EntityTypeBuilder<PlayerCharacter> builder)
    {
        builder.Property(c => c.Name).IsRequired().HasMaxLength(200);
        builder.Property(c => c.PlayerName).HasMaxLength(200);
        builder.Property(c => c.Notes).HasMaxLength(4000);

        builder.OwnsOne(c => c.Abilities, ab =>
        {
            ab.Property(a => a.Strength).HasColumnName("Str");
            ab.Property(a => a.Dexterity).HasColumnName("Dex");
            ab.Property(a => a.Constitution).HasColumnName("Con");
            ab.Property(a => a.Intelligence).HasColumnName("Int");
            ab.Property(a => a.Wisdom).HasColumnName("Wis");
            ab.Property(a => a.Charisma).HasColumnName("Cha");
        });

        builder.HasMany(c => c.Inventory)
            .WithOne(i => i.PlayerCharacter)
            .HasForeignKey(i => i.PlayerCharacterId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
