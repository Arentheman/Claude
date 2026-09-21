using System.ComponentModel.DataAnnotations;

namespace DMA.Domain.Entities;

/// <summary>Owned value object: the five D&amp;D coin denominations a character is carrying.</summary>
public class Currency
{
    [Range(0, int.MaxValue)]
    public int CopperPieces { get; set; }

    [Range(0, int.MaxValue)]
    public int SilverPieces { get; set; }

    [Range(0, int.MaxValue)]
    public int ElectrumPieces { get; set; }

    [Range(0, int.MaxValue)]
    public int GoldPieces { get; set; }

    [Range(0, int.MaxValue)]
    public int PlatinumPieces { get; set; }

    public void Clamp()
    {
        CopperPieces = Math.Max(0, CopperPieces);
        SilverPieces = Math.Max(0, SilverPieces);
        ElectrumPieces = Math.Max(0, ElectrumPieces);
        GoldPieces = Math.Max(0, GoldPieces);
        PlatinumPieces = Math.Max(0, PlatinumPieces);
    }
}
