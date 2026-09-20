namespace DMA.Domain.Entities;

public class Session
{
    public int Id { get; set; }
    public int CampaignId { get; set; }
    public Campaign Campaign { get; set; } = null!;

    public int Number { get; set; }
    public string Title { get; set; } = string.Empty;
    public DateTime? PlayedOn { get; set; }

    /// <summary>What actually happened during the session.</summary>
    public string Summary { get; set; } = string.Empty;

    /// <summary>Private DM notes: hooks, secrets, plans for next time.</summary>
    public string MasterNotes { get; set; } = string.Empty;

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
}
