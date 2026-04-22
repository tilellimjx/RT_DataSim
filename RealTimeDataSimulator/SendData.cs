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
	internal class SendData
	{
		private static readonly HttpClient _httpClient = new() { Timeout = TimeSpan.FromSeconds(30) };
		private static readonly string _endpoint = Environment.GetEnvironmentVariable("HTTP_ENDPOINT") ?? "https://pqxu4yuom8.execute-api.us-east-2.amazonaws.com/version1";
		private static readonly SemaphoreSlim _fileWriteSemaphore = new(1, 1);

		private static async Task LogErrorAsync(int fileIndex, Exception ex, string? payload = null)
		{
			try
			{
				string logPath = $@"C:\Temp\data\SendErrorsLog.txt";
				string timestamp = DateTime.UtcNow.ToString("o");
				string body = $"[{timestamp}] File {fileIndex}: {ex.GetType().FullName}: {ex.Message}\n{ex}\n";
				if (!string.IsNullOrEmpty(payload))
				{
					body += $"Payload: {payload}\n";
				}
				body += "----\n";

				await _fileWriteSemaphore.WaitAsync().ConfigureAwait(false);
				try
				{
					await File.AppendAllTextAsync(logPath, body).ConfigureAwait(false);
				}
				finally
				{
					_fileWriteSemaphore.Release();
				}
			}
			catch
			{
				// best-effort logging; swallow
			}
		}

		internal static async Task StartSending()
		{
			var tasks = new List<Task>();
			for (int fileIndex = 1; fileIndex <= 250; fileIndex++)
			{
				int index = fileIndex; // capture variable for closure
				tasks.Add(SendDataFromFileAsync(index));
			}

			await Task.WhenAll(tasks).ConfigureAwait(false);
		}

		internal static async Task StartSendingSampleAsync(int fileCount)
		{
			var tasks = new List<Task>();
			for (int fileIndex = 1; fileIndex <= fileCount; fileIndex++)
			{
				tasks.Add(SendDataFromFileAsync(fileIndex));
			}
			await Task.WhenAll(tasks).ConfigureAwait(false);
		}

		private static async Task SendDataFromFileAsync(int index)
		{
			string[] fileLines;
			try
			{
				fileLines = File.ReadAllLines($@"C:\Temp\data\datafile_{index}.txt");
			}
			catch (Exception ex)
			{
				await LogErrorAsync(index, ex).ConfigureAwait(false);
				return;
			}

			foreach (string line in fileLines)
			{
				var sw = Stopwatch.StartNew();
				try
				{
					await SendToEndpointAsync(line).ConfigureAwait(false);
				}
				catch (Exception ex)
				{
					await LogErrorAsync(index, ex, line).ConfigureAwait(false);
				}

				sw.Stop();
				var remaining = TimeSpan.FromSeconds(1) - sw.Elapsed;
				if (remaining > TimeSpan.Zero)
				{
					await Task.Delay(remaining).ConfigureAwait(false);
				}
			}
		}

		private static async Task SendToEndpointAsync(string line)
		{
			const int maxAttempts = 3;
			int attempt = 0;
			Exception? lastEx = null;

			while (attempt < maxAttempts)
			{
				attempt++;
				try
				{
					using var content = new StringContent(line, Encoding.UTF8, "application/json");
					var response = await _httpClient.PostAsync(_endpoint, content).ConfigureAwait(false);
					response.EnsureSuccessStatusCode();
					return;
				}
				catch (Exception ex) when (ex is HttpRequestException || ex is TaskCanceledException)
				{
					lastEx = ex;
					if (attempt >= maxAttempts)
					{
						break;
					}
					int delayMs = 500 * (int)Math.Pow(2, attempt - 1);
					await Task.Delay(TimeSpan.FromMilliseconds(delayMs)).ConfigureAwait(false);
					continue;
				}
				catch (Exception ex)
				{
					lastEx = ex;
					break;
				}
			}

			throw lastEx ?? new Exception("Failed sending data to endpoint");
		}
	}
}


