using System.Net;
using DMA.Infrastructure.ExternalReference;

namespace DMA.Tests;

/// <summary>
/// Verifies Open5eReferenceService against real open5e.com response shapes. The JSON below was
/// reconstructed by reading the open5e-api server source (serializers/models) and its actual SRD
/// seed data for Fireball/Goblin, since this test environment can't reach api.open5e.com directly
/// to capture a live response. It pins down the quirks that matter for our mapping: "concentration"
/// and "ritual" are the strings "yes"/"no" (not booleans), "level" is a string like "Cantrip" or
/// "3rd-level" (not numeric), and monster "speed" is a JSON object keyed by movement type.
/// </summary>
public class Open5eReferenceServiceTests
{
    private const string SpellsJson = """
        {
          "count": 1,
          "next": null,
          "previous": null,
          "results": [
            {
              "slug": "fireball",
              "name": "Fireball",
              "desc": "A bright streak flashes from your pointing finger...",
              "range": "150 feet",
              "components": "V, S, M",
              "material": "A tiny ball of bat guano and sulfur.",
              "ritual": "no",
              "duration": "Instantaneous",
              "concentration": "no",
              "casting_time": "1 action",
              "level": "3rd-level",
              "level_int": 3,
              "school": "Evocation",
              "dnd_class": "Sorcerer, Wizard"
            }
          ]
        }
        """;

    private const string CantripSpellJson = """
        {
          "count": 1,
          "next": null,
          "previous": null,
          "results": [
            {
              "slug": "fire-bolt",
              "name": "Fire Bolt",
              "desc": "You hurl a mote of fire...",
              "range": "120 feet",
              "components": "V, S",
              "ritual": "no",
              "duration": "Instantaneous",
              "concentration": "no",
              "casting_time": "1 action",
              "level": "Cantrip",
              "level_int": 0,
              "school": "Evocation",
              "dnd_class": "Sorcerer, Wizard"
            }
          ]
        }
        """;

    private const string MonstersJson = """
        {
          "count": 1,
          "next": null,
          "previous": null,
          "results": [
            {
              "slug": "goblin",
              "desc": "",
              "name": "Goblin",
              "size": "Small",
              "type": "Humanoid",
              "alignment": "neutral evil",
              "armor_class": 15,
              "hit_points": 7,
              "speed": { "walk": 30 },
              "challenge_rating": "1/4",
              "actions": [
                { "name": "Scimitar", "desc": "Melee Weapon Attack: +4 to hit..." },
                { "name": "Shortbow", "desc": "Ranged Weapon Attack: +4 to hit..." }
              ],
              "special_abilities": [
                { "name": "Nimble Escape", "desc": "The goblin can take the Disengage or Hide action as a bonus action on each of its turns." }
              ]
            }
          ]
        }
        """;

    private class StubHandler(string json) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken ct) =>
            Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(json, System.Text.Encoding.UTF8, "application/json")
            });
    }

    private static HttpClient ClientReturning(string json) =>
        new(new StubHandler(json)) { BaseAddress = new Uri("https://api.open5e.com/v1/") };

    [Fact]
    public async Task SearchSpellsAsync_MapsLeveledSpellFields()
    {
        var service = new Open5eReferenceService(ClientReturning(SpellsJson));

        var results = await service.SearchSpellsAsync("fireball");

        var fireball = Assert.Single(results);
        Assert.Equal("Fireball", fireball.Name);
        Assert.Equal("3rd-level", fireball.Level);
        Assert.Equal("Evocation", fireball.School);
        Assert.Equal("Sorcerer, Wizard", fireball.Classes);
        Assert.False(fireball.Concentration);
        Assert.False(fireball.Ritual);
    }

    [Fact]
    public async Task SearchSpellsAsync_PassesThroughCantripLevelLabel()
    {
        var service = new Open5eReferenceService(ClientReturning(CantripSpellJson));

        var results = await service.SearchSpellsAsync("fire bolt");

        Assert.Equal("Cantrip", Assert.Single(results).Level);
    }

    [Fact]
    public async Task SearchMonstersAsync_MapsCoreFieldsAndFormatsSpeedAndDescription()
    {
        var service = new Open5eReferenceService(ClientReturning(MonstersJson));

        var results = await service.SearchMonstersAsync("goblin");

        var goblin = Assert.Single(results);
        Assert.Equal("Goblin", goblin.Name);
        Assert.Equal("1/4", goblin.ChallengeRating);
        Assert.Equal(15, goblin.ArmorClass);
        Assert.Equal(7, goblin.HitPoints);
        Assert.Equal("walk 30 ft.", goblin.Speed);
        Assert.Contains("Nimble Escape", goblin.Description);
        Assert.Contains("Scimitar", goblin.Description);
    }
}
