using DMA.Application.Reference;

namespace DMA.Application.Common.Interfaces;

/// <summary>
/// Read-only lookup against the free, OGL-licensed D&amp;D 5e SRD content (spells, monsters) —
/// not the copyrighted Player's Handbook / Monster Manual text. Requires internet access;
/// implementations should let network failures propagate as exceptions for the caller to handle.
/// </summary>
public interface ISrdReferenceService
{
    Task<IReadOnlyList<SrdSpellSummary>> SearchSpellsAsync(string query, CancellationToken ct = default);

    Task<IReadOnlyList<SrdMonsterSummary>> SearchMonstersAsync(string query, CancellationToken ct = default);
}
