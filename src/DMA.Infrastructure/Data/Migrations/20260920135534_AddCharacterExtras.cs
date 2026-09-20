using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace DMA.Infrastructure.Data.Migrations
{
    /// <inheritdoc />
    public partial class AddCharacterExtras : Migration
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
                name: "CopperPieces",
                table: "PlayerCharacters",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "ElectrumPieces",
                table: "PlayerCharacters",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "GoldPieces",
                table: "PlayerCharacters",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "PlatinumPieces",
                table: "PlayerCharacters",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<string>(
                name: "PortraitPath",
                table: "PlayerCharacters",
                type: "TEXT",
                maxLength: 260,
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "SilverPieces",
                table: "PlayerCharacters",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "Category",
                table: "InventoryItems",
                type: "INTEGER",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.CreateTable(
                name: "CharacterAttachments",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    PlayerCharacterId = table.Column<int>(type: "INTEGER", nullable: false),
                    StoredFileName = table.Column<string>(type: "TEXT", maxLength: 260, nullable: false),
                    OriginalFileName = table.Column<string>(type: "TEXT", maxLength: 260, nullable: false),
                    ContentType = table.Column<string>(type: "TEXT", maxLength: 100, nullable: false),
                    Caption = table.Column<string>(type: "TEXT", maxLength: 500, nullable: false),
                    CreatedAt = table.Column<DateTime>(type: "TEXT", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CharacterAttachments", x => x.Id);
                    table.ForeignKey(
                        name: "FK_CharacterAttachments_PlayerCharacters_PlayerCharacterId",
                        column: x => x.PlayerCharacterId,
                        principalTable: "PlayerCharacters",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateTable(
                name: "CharacterFeatures",
                columns: table => new
                {
                    Id = table.Column<int>(type: "INTEGER", nullable: false)
                        .Annotation("Sqlite:Autoincrement", true),
                    PlayerCharacterId = table.Column<int>(type: "INTEGER", nullable: false),
                    Name = table.Column<string>(type: "TEXT", maxLength: 200, nullable: false),
                    Type = table.Column<int>(type: "INTEGER", nullable: false),
                    Level = table.Column<int>(type: "INTEGER", nullable: true),
                    Description = table.Column<string>(type: "TEXT", maxLength: 4000, nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_CharacterFeatures", x => x.Id);
                    table.ForeignKey(
                        name: "FK_CharacterFeatures_PlayerCharacters_PlayerCharacterId",
                        column: x => x.PlayerCharacterId,
                        principalTable: "PlayerCharacters",
                        principalColumn: "Id",
                        onDelete: ReferentialAction.Cascade);
                });

            migrationBuilder.CreateIndex(
                name: "IX_CharacterAttachments_PlayerCharacterId",
                table: "CharacterAttachments",
                column: "PlayerCharacterId");

            migrationBuilder.CreateIndex(
                name: "IX_CharacterFeatures_PlayerCharacterId",
                table: "CharacterFeatures",
                column: "PlayerCharacterId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "CharacterAttachments");

            migrationBuilder.DropTable(
                name: "CharacterFeatures");

            migrationBuilder.DropColumn(
                name: "CopperPieces",
                table: "PlayerCharacters");

            migrationBuilder.DropColumn(
                name: "ElectrumPieces",
                table: "PlayerCharacters");

            migrationBuilder.DropColumn(
                name: "GoldPieces",
                table: "PlayerCharacters");

            migrationBuilder.DropColumn(
                name: "PlatinumPieces",
                table: "PlayerCharacters");

            migrationBuilder.DropColumn(
                name: "PortraitPath",
                table: "PlayerCharacters");

            migrationBuilder.DropColumn(
                name: "SilverPieces",
                table: "PlayerCharacters");

            migrationBuilder.DropColumn(
                name: "Category",
                table: "InventoryItems");

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
