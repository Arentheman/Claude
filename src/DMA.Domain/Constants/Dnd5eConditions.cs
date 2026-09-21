namespace DMA.Domain.Constants;

/// <summary>The standard D&amp;D 5e condition names, shared between the encounter tracker
/// (combat-scoped conditions) and the campaign page's quick panel (persistent conditions).</summary>
public static class Dnd5eConditions
{
    public static readonly string[] All =
    [
        "Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened", "Grappled", "Incapacitated",
        "Invisible", "Paralyzed", "Petrified", "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious"
    ];
}
