namespace DMA.Domain.Entities;

/// <summary>Owned value object: the five D&amp;D coin denominations a character is carrying.</summary>
public class Currency
{
    public int CopperPieces { get; set; }
    public int SilverPieces { get; set; }
    public int ElectrumPieces { get; set; }
    public int GoldPieces { get; set; }
    public int PlatinumPieces { get; set; }
}
