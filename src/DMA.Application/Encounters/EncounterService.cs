using DMA.Application.Common.Interfaces;
using DMA.Domain.Entities;
using DMA.Domain.Enums;
using Microsoft.EntityFrameworkCore;

namespace DMA.Application.Encounters;

public class EncounterService(IApplicationDbContext db)
{
    public Task<List<Encounter>> GetByCampaignAsync(int campaignId, CancellationToken ct = default) =>
        db.Encounters.Where(e => e.CampaignId == campaignId)
            .OrderByDescending(e => e.CreatedAt)
            .ToListAsync(ct);

    public Task<Encounter?> GetByIdAsync(int id, CancellationToken ct = default) =>
        db.Encounters
            .Include(e => e.Participants.OrderBy(p => p.SortOrder))
            .FirstOrDefaultAsync(e => e.Id == id, ct);

    public async Task<Encounter> CreateAsync(int campaignId, string name, int? sessionId, CancellationToken ct = default)
    {
        var encounter = new Encounter
        {
            CampaignId = campaignId,
            SessionId = sessionId,
            Name = name
        };
        db.Encounters.Add(encounter);
        await db.SaveChangesAsync(ct);
        return encounter;
    }

    public async Task DeleteAsync(int id, CancellationToken ct = default)
    {
        var encounter = await db.Encounters.FindAsync([id], ct);
        if (encounter is null) return;
        db.Encounters.Remove(encounter);
        await db.SaveChangesAsync(ct);
    }

    public async Task<EncounterParticipant> AddFromPlayerCharacterAsync(
        int encounterId, PlayerCharacter character, int initiative, CancellationToken ct = default)
    {
        var participant = new EncounterParticipant
        {
            EncounterId = encounterId,
            SourceType = ParticipantSourceType.PlayerCharacter,
            SourceId = character.Id,
            Name = character.Name,
            Initiative = initiative,
            MaxHp = character.MaxHp,
            CurrentHp = character.CurrentHp,
            ArmorClass = character.ArmorClass
        };
        db.EncounterParticipants.Add(participant);
        await db.SaveChangesAsync(ct);
        return participant;
    }

    public async Task<EncounterParticipant> AddFromStatBlockAsync(
        int encounterId, StatBlock statBlock, int initiative, string? displayName = null, CancellationToken ct = default)
    {
        var participant = new EncounterParticipant
        {
            EncounterId = encounterId,
            SourceType = ParticipantSourceType.StatBlock,
            SourceId = statBlock.Id,
            Name = displayName ?? statBlock.Name,
            Initiative = initiative,
            MaxHp = statBlock.MaxHp,
            CurrentHp = statBlock.MaxHp,
            ArmorClass = statBlock.ArmorClass
        };
        db.EncounterParticipants.Add(participant);
        await db.SaveChangesAsync(ct);
        return participant;
    }

    public async Task<EncounterParticipant> AddCustomAsync(
        int encounterId, string name, int initiative, int maxHp, int armorClass, CancellationToken ct = default)
    {
        maxHp = Math.Max(0, maxHp);
        armorClass = Math.Max(0, armorClass);

        var participant = new EncounterParticipant
        {
            EncounterId = encounterId,
            SourceType = ParticipantSourceType.Custom,
            Name = name,
            Initiative = initiative,
            MaxHp = maxHp,
            CurrentHp = maxHp,
            ArmorClass = armorClass
        };
        db.EncounterParticipants.Add(participant);
        await db.SaveChangesAsync(ct);
        return participant;
    }

    public async Task RemoveParticipantAsync(int participantId, CancellationToken ct = default)
    {
        var participant = await db.EncounterParticipants.FindAsync([participantId], ct);
        if (participant is null) return;
        db.EncounterParticipants.Remove(participant);
        await db.SaveChangesAsync(ct);
    }

    public async Task UpdateHpAsync(int participantId, int currentHp, CancellationToken ct = default)
    {
        var participant = await db.EncounterParticipants.FindAsync([participantId], ct);
        if (participant is null) return;
        participant.CurrentHp = Math.Clamp(currentHp, 0, Math.Max(participant.MaxHp, currentHp));
        await db.SaveChangesAsync(ct);
    }

    public async Task UpdateInitiativeAsync(int participantId, int initiative, CancellationToken ct = default)
    {
        var participant = await db.EncounterParticipants.FindAsync([participantId], ct);
        if (participant is null) return;
        participant.Initiative = initiative;
        await db.SaveChangesAsync(ct);
    }

    public async Task SetActiveAsync(int participantId, bool isActive, CancellationToken ct = default)
    {
        var participant = await db.EncounterParticipants.FindAsync([participantId], ct);
        if (participant is null) return;
        participant.IsActive = isActive;
        await db.SaveChangesAsync(ct);
    }

    public async Task ToggleConditionAsync(int participantId, string condition, CancellationToken ct = default)
    {
        var participant = await db.EncounterParticipants.FindAsync([participantId], ct);
        if (participant is null) return;

        if (!participant.Conditions.Remove(condition))
            participant.Conditions.Add(condition);

        // Force EF to detect the change on the owned JSON-backed collection.
        db.EncounterParticipants.Update(participant);
        await db.SaveChangesAsync(ct);
    }

    /// <summary>Locks in initiative order, sorts participants and starts round 1.</summary>
    public async Task StartAsync(int encounterId, CancellationToken ct = default)
    {
        var encounter = await db.Encounters
            .Include(e => e.Participants)
            .FirstOrDefaultAsync(e => e.Id == encounterId, ct);
        if (encounter is null) return;

        var ordered = encounter.Participants
            .OrderByDescending(p => p.Initiative)
            .ThenBy(p => p.Name)
            .ToList();

        for (var i = 0; i < ordered.Count; i++)
            ordered[i].SortOrder = i;

        encounter.Status = EncounterStatus.Active;
        encounter.CurrentRound = 1;
        encounter.CurrentTurnIndex = 0;
        await db.SaveChangesAsync(ct);
    }

    /// <summary>Advances to the next active participant's turn, rolling into the next round if needed.</summary>
    public async Task NextTurnAsync(int encounterId, CancellationToken ct = default)
    {
        var encounter = await db.Encounters
            .Include(e => e.Participants)
            .FirstOrDefaultAsync(e => e.Id == encounterId, ct);
        if (encounter is null || encounter.Participants.Count == 0) return;

        var ordered = encounter.Participants.OrderBy(p => p.SortOrder).ToList();
        var activeIds = ordered.Where(p => p.IsActive).Select(p => p.Id).ToList();
        if (activeIds.Count == 0) return;

        var currentId = ordered.ElementAtOrDefault(encounter.CurrentTurnIndex)?.Id;
        var currentActiveIndex = currentId is null ? -1 : activeIds.IndexOf(currentId.Value);
        var nextActiveIndex = (currentActiveIndex + 1) % activeIds.Count;

        if (nextActiveIndex <= currentActiveIndex)
            encounter.CurrentRound++;

        var nextParticipantId = activeIds[nextActiveIndex];
        encounter.CurrentTurnIndex = ordered.FindIndex(p => p.Id == nextParticipantId);

        await db.SaveChangesAsync(ct);
    }

    public async Task CompleteAsync(int encounterId, CancellationToken ct = default)
    {
        var encounter = await db.Encounters.FindAsync([encounterId], ct);
        if (encounter is null) return;
        encounter.Status = EncounterStatus.Completed;
        await db.SaveChangesAsync(ct);
    }
}
