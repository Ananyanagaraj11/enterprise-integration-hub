using System.Text.Json;
using Microsoft.AspNetCore.Http.Json;

var builder = WebApplication.CreateBuilder(args);
builder.Services.Configure<JsonOptions>(options =>
{
    options.SerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
});
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyOrigin().AllowAnyHeader().AllowAnyMethod());
});

var app = builder.Build();
app.UseCors();
app.UseDefaultFiles();
app.UseStaticFiles();

var dataDir = Path.Combine(app.Environment.WebRootPath ?? "wwwroot", "data");

app.MapGet("/health", () => Results.Ok(new
{
    status = "ok",
    service = "integration-hub-api",
    stack = "ASP.NET Core 8"
}));

app.MapGet("/api/feeds", (string? status, string? source) =>
{
    var feeds = ReadFeeds(dataDir);
    if (!string.IsNullOrWhiteSpace(status))
        feeds = feeds.Where(f => string.Equals(f.Status, status, StringComparison.OrdinalIgnoreCase)).ToList();
    if (!string.IsNullOrWhiteSpace(source))
        feeds = feeds.Where(f => string.Equals(f.SourceSystem, source, StringComparison.OrdinalIgnoreCase)).ToList();
    return Results.Ok(feeds);
});

app.MapGet("/api/feeds/{feedId}", (string feedId) =>
{
    var feed = ReadFeeds(dataDir).FirstOrDefault(f =>
        string.Equals(f.FeedId, feedId, StringComparison.OrdinalIgnoreCase));
    return feed is null ? Results.NotFound(new { message = "Feed not found", feedId }) : Results.Ok(feed);
});

app.MapGet("/api/summary", () =>
{
    var path = Path.Combine(dataDir, "summary.json");
    if (!File.Exists(path))
        return Results.NotFound(new { message = "Run the Spark ingest job first." });
    using var stream = File.OpenRead(path);
    var summary = JsonSerializer.Deserialize<JsonElement>(stream);
    return Results.Ok(summary);
});

app.Run();

static List<FeedRecord> ReadFeeds(string dataDir)
{
    var path = Path.Combine(dataDir, "feeds.json");
    if (!File.Exists(path))
        return [];
    var json = File.ReadAllText(path);
    return JsonSerializer.Deserialize<List<FeedRecord>>(json, new JsonSerializerOptions
    {
        PropertyNameCaseInsensitive = true
    }) ?? [];
}

public sealed record FeedRecord(
    string FeedId,
    string SourceSystem,
    string Region,
    string Channel,
    double Amount,
    string Status,
    string EventTime
);
