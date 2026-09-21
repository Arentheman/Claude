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
        builder.Property(c => c.PortraitPath).HasMaxLength(260);

        builder.Property(c => c.Conditions)
            .HasConversion(JsonStringListConversion.Converter)
            .Metadata.SetValueComparer(JsonStringListConversion.Comparer);

        builder.OwnsOne(c => c.Abilities, ab =>
        {
            ab.Property(a => a.Strength).HasColumnName("Str");
            ab.Property(a => a.Dexterity).HasColumnName("Dex");
            ab.Property(a => a.Constitution).HasColumnName("Con");
            ab.Property(a => a.Intelligence).HasColumnName("Int");
            ab.Property(a => a.Wisdom).HasColumnName("Wis");
            ab.Property(a => a.Charisma).HasColumnName("Cha");
        });

        builder.OwnsOne(c => c.Currency, cur =>
        {
            cur.Property(c => c.CopperPieces).HasColumnName("CopperPieces");
            cur.Property(c => c.SilverPieces).HasColumnName("SilverPieces");
            cur.Property(c => c.ElectrumPieces).HasColumnName("ElectrumPieces");
            cur.Property(c => c.GoldPieces).HasColumnName("GoldPieces");
            cur.Property(c => c.PlatinumPieces).HasColumnName("PlatinumPieces");
        });

        builder.HasMany(c => c.Inventory)
            .WithOne(i => i.PlayerCharacter)
            .HasForeignKey(i => i.PlayerCharacterId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasMany(c => c.Features)
            .WithOne(f => f.PlayerCharacter)
            .HasForeignKey(f => f.PlayerCharacterId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasMany(c => c.Attachments)
            .WithOne(a => a.PlayerCharacter)
            .HasForeignKey(a => a.PlayerCharacterId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
