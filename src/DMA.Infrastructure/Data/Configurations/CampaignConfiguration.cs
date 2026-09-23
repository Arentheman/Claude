using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class CampaignConfiguration : IEntityTypeConfiguration<Campaign>
{
    public void Configure(EntityTypeBuilder<Campaign> builder)
    {
        builder.Property(c => c.Name).IsRequired().HasMaxLength(200);
        builder.Property(c => c.Description).HasMaxLength(4000);

        builder.HasMany(c => c.Sessions)
            .WithOne(s => s.Campaign)
            .HasForeignKey(s => s.CampaignId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasMany(c => c.PlayerCharacters)
            .WithOne(p => p.Campaign)
            .HasForeignKey(p => p.CampaignId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasMany(c => c.Encounters)
            .WithOne(e => e.Campaign)
            .HasForeignKey(e => e.CampaignId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasMany(c => c.StoryNodes)
            .WithOne(n => n.Campaign)
            .HasForeignKey(n => n.CampaignId)
            .OnDelete(DeleteBehavior.Cascade);

        // SetNull, not Cascade: deleting the master Story shouldn't take the campaign (or its
        // already-copied CampaignStoryNode tree) down with it — the copy is independent by design.
        builder.HasOne(c => c.SourceStory)
            .WithMany()
            .HasForeignKey(c => c.SourceStoryId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
