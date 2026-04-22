namespace RealTimeDataSimulator
{
    internal class Program
    {
        static void Main(string[] args)
        {
            if (args.Length > 0 && args[0] == "create")
            {
                CreateData.GenerateData();
            }
            else if (args.Length > 0 && args[0] == "send")
            {
                // Start sending (full set)
                SendData.StartSending().GetAwaiter().GetResult();
            }
            else if (args.Length > 0 && args[0] == "send-sample")
            {
                // run a small sample to validate behavior: default 2 files
                int count = 2;
                if (args.Length > 1 && int.TryParse(args[1], out var c))
                {
                    count = c;
                }
                SendData.StartSendingSampleAsync(count).GetAwaiter().GetResult();
            }
            else
            {
                Console.WriteLine("Usage: RealTimeDataSimulator create|send|send-sample [count]");
            }
        }
    }
}
