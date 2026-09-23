using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace DMA.Infrastructure.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddStoryTree : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AlterColumn<int>(
                name: "Id",
                table: "PlayerCharacters",
                type: "INTEGER",
                nullable: false,
                oldClrType: typeof(int),
                oldType: "INTEGER")
                .OldAnnotation("Sqlite:Autoincrement", true);

            migrationBuilder.AddColumn<int>(
                name: "SourceStoryId",
                table: "Campaigns",
                type: "INTEGER",
                nullable: true);

            migrationBuilder.CreateTable(
                name: "Stories",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    Name = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Description = table.Column<string>(type: "TEXT", maxLength: 4000, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_Stories", x => x.Id);
                });

            migrationBuilder.CreateTable(
                name: "StoryNodes",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    StoryId = table.Column<int>(type: "INTEGER", nullable: false),
                    ParentNodeId = table.Column<int>(type: "INTEGER", nullable: true),
                    Title = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Description = table.Column<string>(type: "TEXT", maxLength: 8000, nullable: false),
                    PlannedEncounters = table.Column<string>(type: "TEXT", maxLength: 4000, nullable: false),
                    PlannedLoot = table.Column<string>(type: "TEXT", maxLength: 4000, nullable: false),
                    SortOrder = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_StoryNodes", x => x.Id);
                    table.ForeignKey(
                        name: "FK_StoryNodes_Stories_StoryId",
                        column: x => x.StoryId,
                        principalTable: "Stories",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_StoryNodes_StoryNodes_ParentNodeId",
                        column: x => x.ParentNodeId,
                        principalTable: "StoryNodes",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                });

            migrationBuilder.CreateTable(
                name: "CampaignStoryNodes",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    CampaignId = table.Column<int>(type: "INTEGER", nullable: false),
                    ParentNodeId = table.Column<int>(type: "INTEGER", nullable: true),
                    SourceStoryNodeId = table.Column<int>(type: "INTEGER", nullable: true),
                    Title = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Description = table.Column<string>(type: "TEXT", maxLength: 8000, nullable: false),
                    PlannedEncounters = table.Column<string>(type: "TEXT", maxLength: 4000, nullable: false),
                    PlannedLoot = table.Column<string>(type: "TEXT", maxLength: 4000, nullable: false),
                    SortOrder = table.Column<int>(type: "INTEGER", nullable: false),
                    Status = table.Column<int>(type: "INTEGER", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CampaignStoryNodes", x => x.Id);
                    table.ForeignKey(
                        name: "FK_CampaignStoryNodes_CampaignStoryNodes_ParentNodeId",
                        column: x => x.ParentNodeId,
                        principalTable: "CampaignStoryNodes",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Restrict);
                    table.ForeignKey(
                        name: "FK_CampaignStoryNodes_Campaigns_CampaignId",
                        column: x => x.CampaignId,
                        principalTable: "Campaigns",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                    table.ForeignKey(
                        name: "FK_CampaignStoryNodes_StoryNodes_SourceStoryNodeId",
                        column: x => x.SourceStoryNodeId,
                        principalTable: "StoryNodes",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.SetNull);
                });

            migrationBuilder.CreateIndex(
                name: "IX_Campaigns_SourceStoryId",
                table: "Campaigns",
                column: "SourceStoryId");

            migrationBuilder.CreateIndex(
                name: "IX_CampaignStoryNodes_CampaignId",
                table: "CampaignStoryNodes",
                column: "CampaignId");

            migrationBuilder.CreateIndex(
                name: "IX_CampaignStoryNodes_ParentNodeId",
                table: "CampaignStoryNodes",
                column: "ParentNodeId");

            migrationBuilder.CreateIndex(
                name: "IX_CampaignStoryNodes_SourceStoryNodeId",
                table: "CampaignStoryNodes",
                column: "SourceStoryNodeId");

            migrationBuilder.CreateIndex(
                name: "IX_StoryNodes_ParentNodeId",
                table: "StoryNodes",
                column: "ParentNodeId");

            migrationBuilder.CreateIndex(
                name: "IX_StoryNodes_StoryId",
                table: "StoryNodes",
                column: "StoryId");

            migrationBuilder.AddForeignKey(
                name: "FK_Campaigns_Stories_SourceStoryId",
                table: "Campaigns",
                column: "SourceStoryId",
                principalTable: "Stories",
                principalColumn: "Id",
                onDelete: ReferentialAction.SetNull);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Campaigns_Stories_SourceStoryId",
                table: "Campaigns");

            migrationBuilder.DropTable(
                name: "CampaignStoryNodes");

            migrationBuilder.DropTable(
                name: "StoryNodes");

            migrationBuilder.DropTable(
                name: "Stories");

            migrationBuilder.DropIndex(
                name: "IX_Campaigns_SourceStoryId",
                table: "Campaigns");

            migrationBuilder.DropColumn(
                name: "SourceStoryId",
                table: "Campaigns");

            migrationBuilder.AlterColumn<int>(
                name: "Id",
                table: "PlayerCharacters",
                type: "INTEGER",
                nullable: false,
                oldClrType: typeof(int),
                oldType: "INTEGER")
                .Annotation("Sqlite:Autoincrement", true);
        }
    }
}
