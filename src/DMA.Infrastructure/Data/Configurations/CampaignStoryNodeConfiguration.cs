using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class CampaignStoryNodeConfiguration : IEntityTypeConfiguration<CampaignStoryNode>
{
    public void Configure(EntityTypeBuilder<CampaignStoryNode> builder)
    {
        builder.Property(n => n.Title).IsRequired().HasMaxLength(200);
        builder.Property(n => n.Description).HasMaxLength(8000);
        builder.Property(n => n.PlannedEncounters).HasMaxLength(4000);
        builder.Property(n => n.PlannedLoot).HasMaxLength(4000);

        // Restrict for the same reason as StoryNode's self-reference: the service layer deletes
        // subtrees bottom-up rather than relying on a self-referencing cascade.
        builder.HasOne(n => n.ParentNode)
            .WithMany(n => n.Children)
            .HasForeignKey(n => n.ParentNodeId)
            .OnDelete(DeleteBehavior.Restrict);

        // No navigation to the source node on purpose — this is a one-way "where did this come
        // from" pointer for the manual pull-updates tool, not a live relationship. SetNull so a
        // deleted master node doesn't take the campaign's own copy down with it.
        builder.HasOne<StoryNode>()
            .WithMany()
            .HasForeignKey(n => n.SourceStoryNodeId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
