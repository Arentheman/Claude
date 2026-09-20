using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class CharacterAttachmentConfiguration : IEntityTypeConfiguration<CharacterAttachment>
{
    public void Configure(EntityTypeBuilder<CharacterAttachment> builder)
    {
        builder.Property(a => a.StoredFileName).IsRequired().HasMaxLength(260);
        builder.Property(a => a.OriginalFileName).IsRequired().HasMaxLength(260);
        builder.Property(a => a.ContentType).HasMaxLength(100);
        builder.Property(a => a.Caption).HasMaxLength(500);
    }
}
