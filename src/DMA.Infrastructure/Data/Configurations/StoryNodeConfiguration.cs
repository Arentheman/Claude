using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class StoryNodeConfiguration : IEntityTypeConfiguration<StoryNode>
{
    public void Configure(EntityTypeBuilder<StoryNode> builder)
    {
        builder.Property(n => n.Title).IsRequired().HasMaxLength(200);
        builder.Property(n => n.Description).HasMaxLength(20000);
        builder.Property(n => n.PlannedLoot).HasMaxLength(4000);

        // Restrict (not Cascade): a node with children can't be deleted directly — the service
        // layer deletes the subtree bottom-up first. Avoids relying on SQLite to walk a
        // self-referencing cascade correctly.
        builder.HasOne(n => n.ParentNode)
            .WithMany(n => n.Children)
            .HasForeignKey(n => n.ParentNodeId)
            .OnDelete(DeleteBehavior.Restrict);
    }
}
