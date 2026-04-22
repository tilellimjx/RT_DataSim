using System;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using System.Collections.Generic;

namespace RealTimeDataSimulator
{
`tinternal class SendData
`t{
`t`tprivate static readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(30) };
`t`tprivate static readonly string _endpoint = Environment.GetEnvironmentVariable("HTTP_ENDPOINT") ?? "https://pqxu4yuom8.execute-api.us-east-2.amazonaws.com/version1";
`t`tprivate static readonly SemaphoreSlim _fileWriteSemaphore = new(1, 1);

`t`tprivate static async Task LogErrorAsync(int fileIndex, Exception ex, string? payload = null)
`t`t{
`t`t`ttry
`t`t`t{
`t`t`t`tstring logPath = $@"C:\Temp\data\SendErrorsLog.txt";
`t`t`t`tstring timestamp = DateTime.UtcNow.ToString("o");
`t`t`t`tstring body = $"[{timestamp}] File {fileIndex}: {ex.GetType().FullName}: {ex.Message}\n{ex}\n";
`t`t`t`tif (!string.IsNullOrEmpty(payload))
`t`t`t`t{
`t`t`t`t`tbody += $"Payload: {payload}\n";
`t`t`t`t}
`t`t`t`tbody += "----\n";

`t`t`t`tawait _fileWriteSemaphore.WaitAsync().ConfigureAwait(false);
`t`t`t`ttry
`t`t`t`t{
`t`t`t`t`tawait File.AppendAllTextAsync(logPath, body).ConfigureAwait(false);
`t`t`t`t}
`t`t`t`tfinally
`t`t`t`t{
`t`t`t`t`t_fileWriteSemaphore.Release();
`t`t`t`t}
`t`t`t}
`t`t`tcatch
`t`t`t{
`t`t`t`t// best-effort logging; swallow
`t`t`t}
`t`t}

`t`tinternal static async Task StartSending()
`t`t{
`t`t`tvar tasks = new List<Task>();
`t`t`tfor (int fileIndex = 1; fileIndex <= 250; fileIndex++)
`t`t`t{
`t`t`t`tint index = fileIndex; // capture variable for closure
`t`t`t`ttasks.Add(SendDataFromFileAsync(index));
`t`t`t}

`t`t`tawait Task.WhenAll(tasks).ConfigureAwait(false);
`t`t}

`t`tinternal static async Task StartSendingSampleAsync(int fileCount)
`t`t{
`t`t`tvar tasks = new List<Task>();
`t`t`tfor (int fileIndex = 1; fileIndex <= fileCount; fileIndex++)
`t`t`t{
`t`t`t`ttasks.Add(SendDataFromFileAsync(fileIndex));
`t`t`t}
`t`t`tawait Task.WhenAll(tasks).ConfigureAwait(false);
`t`t}

`t`tprivate static async Task SendDataFromFileAsync(int index)
`t`t{
`t`t`tstring[] fileLines;
`t`t`ttry
`t`t`t{
`t`t`t`tfileLines = File.ReadAllLines($@"C:\Temp\data\datafile_{index}.txt");
`t`t`t}
`t`t`tcatch (Exception ex)
`t`t`t{
`t`t`t`tawait LogErrorAsync(index, ex).ConfigureAwait(false);
`t`t`t`treturn;
`t`t`t}

`t`t`tforeach (string line in fileLines)
`t`t`t{
`t`t`t`tvar sw = Stopwatch.StartNew();
`t`t`t`ttry
`t`t`t`t{
`t`t`t`t`tawait SendToEndpointAsync(line).ConfigureAwait(false);
`t`t`t`t}
`t`t`t`tcatch (Exception ex)
`t`t`t`t{
`t`t`t`t`tawait LogErrorAsync(index, ex, line).ConfigureAwait(false);
`t`t`t`t}

`t`t`t`tsw.Stop();
`t`t`t`tvar remaining = TimeSpan.FromSeconds(1) - sw.Elapsed;
`t`t`t`tif (remaining > TimeSpan.Zero)
`t`t`t`t{
`t`t`t`t`tawait Task.Delay(remaining).ConfigureAwait(false);
`t`t`t`t}
`t`t`t}
`t`t}

`t`tprivate static async Task SendToEndpointAsync(string line)
`t`t{
`t`t`tconst int maxAttempts = 3;
`t`t`tint attempt = 0;
`t`t`tException? lastEx = null;

`t`t`twhile (attempt < maxAttempts)
`t`t`t{
`t`t`t`tattempt++;
`t`t`t`ttry
`t`t`t`t{
`t`t`t`t`tusing var content = new StringContent(line, Encoding.UTF8, "application/json");
`t`t`t`t`tvar response = await _httpClient.PostAsync(_endpoint, content).ConfigureAwait(false);
`t`t`t`t`tresponse.EnsureSuccessStatusCode();
`t`t`t`t`treturn;
`t`t`t`t}
`t`t`t`tcatch (Exception ex) when (ex is HttpRequestException || ex is TaskCanceledException)
`t`t`t`t{
`t`t`t`t`tlastEx = ex;
`t`t`t`t`tif (attempt >= maxAttempts)
`t`t`t`t`t{
`t`t`t`t`t`tbreak;
`t`t`t`t`t}
`t`t`t`t`tint delayMs = 500 * (int)Math.Pow(2, attempt - 1);
`t`t`t`t`tawait Task.Delay(TimeSpan.FromMilliseconds(delayMs)).ConfigureAwait(false);
`t`t`t`t`tcontinue;
`t`t`t`t}
`t`t`t`tcatch (Exception ex)
`t`t`t`t{
`t`t`t`t`tlastEx = ex;
`t`t`t`t`tbreak;
`t`t`t`t}
`t`t`t}

`t`t`tthrow lastEx ?? new Exception("Failed sending data to endpoint");
`t`t}
`t}
}

