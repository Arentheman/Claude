FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

COPY DungeonMasterAssistant.sln .
COPY src/DMA.Domain/DMA.Domain.csproj src/DMA.Domain/
COPY src/DMA.Application/DMA.Application.csproj src/DMA.Application/
COPY src/DMA.Infrastructure/DMA.Infrastructure.csproj src/DMA.Infrastructure/
COPY src/DMA.Web/DMA.Web.csproj src/DMA.Web/
COPY tests/DMA.Tests/DMA.Tests.csproj tests/DMA.Tests/
RUN dotnet restore src/DMA.Web/DMA.Web.csproj

COPY . .
RUN dotnet publish src/DMA.Web/DMA.Web.csproj -c Release -o /app --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS runtime
WORKDIR /app
COPY --from=build /app .

ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "DMA.Web.dll"]
