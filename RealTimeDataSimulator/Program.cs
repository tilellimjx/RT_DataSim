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
                SendData.StartSending();
            }
            else
            {
                Console.WriteLine("Usage: RealTimeDataSimulator create|send");
            }
        }
    }
}
