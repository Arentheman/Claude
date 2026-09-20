using DMA.Domain.Entities;
using DMA.Domain.Enums;

namespace DMA.Infrastructure.Data.Seed;

/// <summary>
/// A handful of monsters from the D&amp;D 5e System Reference Document (SRD),
/// open game content usable under the OGL, to give a new bestiary something to start from.
/// </summary>
public static class SrdMonsterSeed
{
    public static IReadOnlyList<StatBlock> GetMonsters() =>
    [
        new StatBlock
        {
            Name = "Goblin",
            Type = StatBlockType.Monster,
            ChallengeRating = "1/4",
            MaxHp = 7,
            ArmorClass = 15,
            Speed = "30 ft.",
            Abilities = new AbilityScores { Strength = 8, Dexterity = 14, Constitution = 10, Intelligence = 10, Wisdom = 8, Charisma = 8 },
            Description = "Small humanoid, neutral evil. Nimble Escape: can Disengage or Hide as a bonus action.",
            Source = "SRD 5.1"
        },
        new StatBlock
        {
            Name = "Skeleton",
            Type = StatBlockType.Monster,
            ChallengeRating = "1/4",
            MaxHp = 13,
            ArmorClass = 13,
            Speed = "30 ft.",
            Abilities = new AbilityScores { Strength = 10, Dexterity = 14, Constitution = 15, Intelligence = 6, Wisdom = 8, Charisma = 5 },
            Description = "Medium undead, lawful evil. Vulnerable to bludgeoning damage.",
            Source = "SRD 5.1"
        },
        new StatBlock
        {
            Name = "Orc",
            Type = StatBlockType.Monster,
            ChallengeRating = "1/2",
            MaxHp = 15,
            ArmorClass = 13,
            Speed = "30 ft.",
            Abilities = new AbilityScores { Strength = 16, Dexterity = 12, Constitution = 16, Intelligence = 7, Wisdom = 11, Charisma = 10 },
            Description = "Medium humanoid, chaotic evil. Aggressive: can move toward an enemy as a bonus action.",
            Source = "SRD 5.1"
        },
        new StatBlock
        {
            Name = "Wolf",
            Type = StatBlockType.Monster,
            ChallengeRating = "1/4",
            MaxHp = 11,
            ArmorClass = 13,
            Speed = "40 ft.",
            Abilities = new AbilityScores { Strength = 12, Dexterity = 15, Constitution = 12, Intelligence = 3, Wisdom = 12, Charisma = 6 },
            Description = "Medium beast, unaligned. Pack Tactics: advantage on attacks if an ally is nearby.",
            Source = "SRD 5.1"
        },
        new StatBlock
        {
            Name = "Zombie",
            Type = StatBlockType.Monster,
            ChallengeRating = "1/4",
            MaxHp = 22,
            ArmorClass = 8,
            Speed = "20 ft.",
            Abilities = new AbilityScores { Strength = 13, Dexterity = 6, Constitution = 16, Intelligence = 3, Wisdom = 6, Charisma = 5 },
            Description = "Medium undead, neutral evil. Undead Fortitude: can shrug off a killing blow on a Constitution save.",
            Source = "SRD 5.1"
        },
        new StatBlock
        {
            Name = "Bandit",
            Type = StatBlockType.Npc,
            ChallengeRating = "1/8",
            MaxHp = 11,
            ArmorClass = 12,
            Speed = "30 ft.",
            Abilities = new AbilityScores { Strength = 11, Dexterity = 12, Constitution = 12, Intelligence = 10, Wisdom = 10, Charisma = 10 },
            Description = "Medium humanoid, any non-lawful alignment. A common human NPC adversary.",
            Source = "SRD 5.1"
        }
    ];
}
