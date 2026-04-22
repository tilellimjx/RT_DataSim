namespace RealTimeDataSimulator
{
    internal class SendData
    {
        private static readonly System.Net.Http.HttpClient _httpClient = new() { Timeout = System.TimeSpan.FromSeconds(30) };
        private static readonly string _endpoint = System.Environment.GetEnvironmentVariable("HTTP_ENDPOINT") ?? "https://pqxu4yuom8.execute-api.us-east-2.amazonaws.com/version1";
        private static readonly System.Threading.SemaphoreSlim _fileWriteSemaphore = new(1, 1);

        private static async System.Threading.Tasks.Task LogErrorAsync(int fileIndex, System.Exception ex, string? payload = null)
        {
            try
            {
                string logPath = $@"C:\Temp\data\SendErrorsLog.txt";
                string timestamp = System.DateTime.UtcNow.ToString("o");
                string body = $"[{timestamp}] File {fileIndex}: {ex.GetType().FullName}: {ex.Message}\n{ex}\n";
                if (!string.IsNullOrEmpty(payload))
                {
                    body += $"Payload: {payload}\n";
                }
                body += "----\n";

                await _fileWriteSemaphore.WaitAsync().ConfigureAwait(false);
                try
                {
                    await System.IO.File.AppendAllTextAsync(logPath, body).ConfigureAwait(false);
                }
                finally
                {
                    _fileWriteSemaphore.Release();
                }
            }
            catch
            {
                // best-effort logging; swallow to avoid recursive failures
            }
        }

        internal static async System.Threading.Tasks.Task StartSending()
        {
            // spawn 250 parallel tasks to read and send data from each file
            var tasks = new System.Collections.Generic.List<System.Threading.Tasks.Task>();
            for (int fileIndex = 1; fileIndex <= 250; fileIndex++)
            {
                int index = fileIndex; // capture variable for closure
                tasks.Add(SendDataFromFileAsync(index));
            }

            await System.Threading.Tasks.Task.WhenAll(tasks).ConfigureAwait(false);
        }

        internal static async System.Threading.Tasks.Task StartSendingSampleAsync(int fileCount)
        {
            var tasks = new System.Collections.Generic.List<System.Threading.Tasks.Task>();
            for (int fileIndex = 1; fileIndex <= fileCount; fileIndex++)
            {
                tasks.Add(SendDataFromFileAsync(fileIndex));
            }
            await System.Threading.Tasks.Task.WhenAll(tasks).ConfigureAwait(false);
        }

        private static async System.Threading.Tasks.Task SendDataFromFileAsync(int index)
        {
            string[] fileLines;
            try
            {
                fileLines = System.IO.File.ReadAllLines($@"C:\Temp\data\datafile_{index}.txt");
            }
            catch (System.Exception ex)
            {
                await LogErrorAsync(index, ex).ConfigureAwait(false);
                return;
            }

            foreach (string line in fileLines)
            {
                var sw = System.Diagnostics.Stopwatch.StartNew();
                try
                {
                    // send data asynchronously to endpoint with retries inside the method
                    await SendToEndpointAsync(line).ConfigureAwait(false);
                }
                catch (System.Exception ex)
                {
                    // log any exceptions during sending (including failed retries)
                    await LogErrorAsync(index, ex, line).ConfigureAwait(false);
                }

                sw.Stop();
                var remaining = System.TimeSpan.FromSeconds(1) - sw.Elapsed;
                if (remaining > System.TimeSpan.Zero)
                {
                    await System.Threading.Tasks.Task.Delay(remaining).ConfigureAwait(false);
                }
            }
        }

        private static async System.Threading.Tasks.Task SendToEndpointAsync(string line)
        {
            const int maxAttempts = 3;
            int attempt = 0;
            System.Exception? lastEx = null;

            while (attempt < maxAttempts)
            {
                attempt++;
                try
                {
                    using var content = new System.Net.Http.StringContent(line, System.Text.Encoding.UTF8, "application/json");
                    var response = await _httpClient.PostAsync(_endpoint, content).ConfigureAwait(false);
                    response.EnsureSuccessStatusCode();
                    return;
                }
                catch (System.Exception ex) when (ex is System.Net.Http.HttpRequestException || ex is System.Threading.Tasks.TaskCanceledException)
                {
                    lastEx = ex;
                    if (attempt >= maxAttempts)
                    {
                        break;
                    }
                    // exponential backoff (in ms): 500, 1000, 2000... (attempt starts at 1)
                    int delayMs = 500 * (int)System.Math.Pow(2, attempt - 1);
                    await System.Threading.Tasks.Task.Delay(System.TimeSpan.FromMilliseconds(delayMs)).ConfigureAwait(false);
                    continue;
                }
                catch (System.Exception ex)
                {
                    // non-transient error - capture and break
                    lastEx = ex;
                    break;
                }
            }

            // if we reach here, all attempts failed
            throw lastEx ?? new System.Exception("Failed sending data to endpoint");
        }
    }
}
