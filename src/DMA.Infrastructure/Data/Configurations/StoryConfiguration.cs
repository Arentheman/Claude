using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class StoryConfiguration : IEntityTypeConfiguration<Story>
{
    public void Configure(EntityTypeBuilder<Story> builder)
    {
        builder.Property(s => s.Name).IsRequired().HasMaxLength(200);
        builder.Property(s => s.Description).HasMaxLength(4000);

        builder.HasMany(s => s.Nodes)
            .WithOne(n => n.Story)
            .HasForeignKey(n => n.StoryId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
