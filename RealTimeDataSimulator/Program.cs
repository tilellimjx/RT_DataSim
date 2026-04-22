using System;

namespace RealTimeDataSimulator
{
`tinternal class Program
`t{
`t`tstatic void Main(string[] args)
`t`t{
`t`t`tif (args.Length > 0 && args[0] == "create")
`t`t`t{
`t`t`t`tCreateData.GenerateData();
`t`t`t}
`t`t`telse if (args.Length > 0 && args[0] == "send")
`t`t`t{
`t`t`t`t// Start sending (full set)
`t`t`t`tSendData.StartSending().GetAwaiter().GetResult();
`t`t`t}
`t`t`telse if (args.Length > 0 && args[0] == "send-sample")
`t`t`t{
`t`t`t`t// run a small sample to validate behavior: default 2 files
`t`t`t`tint count = 2;
`t`t`t`tif (args.Length > 1 && int.TryParse(args[1], out var c))
`t`t`t`t{
`t`t`t`t`tcount = c;
`t`t`t`t}
`t`t`t`tSendData.StartSendingSampleAsync(count).GetAwaiter().GetResult();
`t`t`t}
`t`t`telse
`t`t`t{
`t`t`t`tConsole.WriteLine("Usage: RealTimeDataSimulator create|send|send-sample [count]");
`t`t`t}
`t`t}
`t}
}

