using DMA.Domain.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;

namespace DMA.Infrastructure.Data.Configurations;

public class SessionConfiguration : IEntityTypeConfiguration<Session>
{
    public void Configure(EntityTypeBuilder<Session> builder)
    {
        builder.Property(s => s.Title).IsRequired().HasMaxLength(200);
        builder.Property(s => s.Summary).HasMaxLength(8000);
        builder.Property(s => s.MasterNotes).HasMaxLength(8000);
    }
}
