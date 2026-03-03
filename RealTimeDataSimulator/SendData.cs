namespace RealTimeDataSimulator
{
    internal class SendData
    {
        internal static async Task StartSending()
        {
            // spawn 250 parallel tasks to read and send data from each file
            for (int fileIndex = 1; fileIndex <= 250; fileIndex++)
            {
                int index = fileIndex; // capture variable for closure
                await Task.Run(() => SendDataFromFile(index)).ConfigureAwait(false);
            }
        }

        private static void SendDataFromFile(int index)
        {
            string[] fileLines = File.ReadAllLines($@"C:\Temp\data\datafile_{index}.txt");
            foreach (string line in fileLines)
            {
                long startTicks = DateTime.Now.Ticks;
                try
                {
                    // simulate sending data to endpoint
                    SendToEndpoint(line);
                }
                catch (Exception ex)
                {
                    // log any exceptions during sending
                    File.AppendAllText($@"C:\Temp\data\SendErrorsLog.txt", $"Error sending data from file {index}: {ex.Message}{Environment.NewLine}");
                }

                long elapsedTicks = DateTime.Now.Ticks - startTicks;

                // ensure one second interval between sends
                if (elapsedTicks < TimeSpan.TicksPerSecond)
                {
                    long sleepMillis = (TimeSpan.TicksPerSecond - elapsedTicks) / TimeSpan.TicksPerMillisecond;
                    Thread.Sleep((int)sleepMillis);
                }
            }
        }

        private static void SendToEndpoint(string line)
        {
            // send the data line to a REST API endpoint
            HttpClient client = new();
            var content = new StringContent(line, System.Text.Encoding.UTF8, "application/json");
            var response = client.PostAsync("https://example.com/api/data", content).Result;
            response.EnsureSuccessStatusCode();
        }
    }
}
