using System;
using System.IO;
using System.Text.Json;

namespace RealTimeDataSimulator
{
`tinternal class CreateData
`t{
`t`tprivate enum EProps
`t`t{
`t`t`ttemperature,
`t`t`thumidity,
`t`t`tbattery_level,
`t`t`tlongitude,
`t`t`tlatitude,
`t`t}

`t`tinternal static void GenerateData()
`t`t{
`t`t`tif (!Directory.Exists($@"C:\Temp\data"))
`t`t`t{
`t`t`t`tDirectory.CreateDirectory($@"C:\Temp\data");
`t`t`t}

`t`t`tif (File.Exists($@"C:\Temp\data\CorruptionLog.txt"))
`t`t`t{
`t`t`t`tFile.Delete($@"C:\Temp\data\CorruptionLog.txt");
`t`t`t}

`t`t`tfor (int fileIndex = 1; fileIndex <= 250; fileIndex++)
`t`t`t{
`t`t`t`tvar f = File.Create($@"C:\Temp\data\datafile_{fileIndex}.txt");
`t`t`t`tusing StreamWriter writer = new(f);
`t`t`t`tfor (int second = 0; second < 7200; second++)
`t`t`t`t{
`t`t`t`t`tstring status = CreateStatus();
`t`t`t`t`tRTData data = new()
`t`t`t`t`t{
`t`t`t`t`t`tdevice_id = $"Sensor_{fileIndex}",
`t`t`t`t`t`ttimestamp = DateTime.UtcNow,
`t`t`t`t`t`ttemperature = GetTemperature(status),
`t`t`t`t`t`thumidity = GetHumidity(status),
`t`t`t`t`t`tbattery_level = GetBatteryLevel(status),
`t`t`t`t`t`tlocation = new()
`t`t`t`t`t`t{
`t`t`t`t`t`t`tlatitude = GetLatitude(status),
`t`t`t`t`t`t`tlongitude = GetLongitude(status)
`t`t`t`t`t`t},
`t`t`t`t`t`tstatus = status
`t`t`t`t`t};

`t`t`t`t`tIntroducePossibleCorruption(ref data);

`t`t`t`t`tstring line = JsonSerializer.Serialize(data);
`t`t`t`t`twriter.WriteLine(line);
`t`t`t`t}

`t`t`t`twriter.Flush();
`t`t`t`twriter.Close();
`t`t`t`tf.Close();

`t`t`t`tvar fw = File.Open($@"C:\Temp\data\CorruptionLog.txt", FileMode.OpenOrCreate, FileAccess.Write);
`t`t`t`tfw.Seek(0, SeekOrigin.End);
`t`t`t`tusing StreamWriter sw = new(fw);
`t`t`t`tsw.WriteLine($"Number of corrupted entries in file {fileIndex}: {_corruptionCounter}");
`t`t`t`tsw.Flush();
`t`t`t`tsw.Close();
`t`t`t`tfw.Close();

`t`t`t`t_LastTemp = 0;
`t`t`t`t_LastHumidity = 0;
`t`t`t`t_LastBatteryLevel = 0;
`t`t`t`t_LastLongitude = 0;
`t`t`t`t_LastLatitude = 0;
`t`t`t`t_corruptionCounter = 0;
`t`t`t}
`t`t}

`t`tprivate static int _corruptionCounter = 0;
`t`tprivate static void IntroducePossibleCorruption(ref RTData data)
`t`t{
`t`t`tRandom rand = new();
`t`t`tint value = rand.Next(1, 1001);
`t`t`tif (value == 1)
`t`t`t{
`t`t`t`tdata.temperature = decimal.MinValue;
`t`t`t}
`t`t`telse if (value == 2)
`t`t`t{
`t`t`t`tdata.humidity = decimal.MinValue;
`t`t`t}
`t`t`telse if (value == 3)
`t`t`t{
`t`t`t`tdata.battery_level = decimal.MinValue;
`t`t`t}
`t`t`telse if (value == 4)
`t`t`t{
`t`t`t`tdata.location.latitude = decimal.MinValue;
`t`t`t}
`t`t`telse if (value == 5)
`t`t`t{
`t`t`t`tdata.location.longitude = decimal.MinValue;
`t`t`t}

`t`t`tif (value <= 5)
`t`t`t{
`t`t`t`t_corruptionCounter++;
`t`t`t}
`t`t}

`t`tprivate static EProps _LastPropError = EProps.temperature;
`t`tprivate static void GetNextPropError()
`t`t{
`t`t`tif (_LastPropError == EProps.latitude)
`t`t`t{
`t`t`t`t_LastPropError = EProps.temperature;
`t`t`t}
`t`t`telse
`t`t`t{
`t`t`t`t_LastPropError++;
`t`t`t}
`t`t}

`t`tprivate static string CreateStatus()
`t`t{
`t`t`tRandom rand = new();
`t`t`tint value = rand.Next(1, 101);
`t`t`tif (value <= 92)
`t`t`t{
`t`t`t`treturn "OK";
`t`t`t}
`t`t`telse if (value <= 98)
`t`t`t{
`t`t`t`treturn "WARN";
`t`t`t}
`t`t`telse
`t`t`t{
`t`t`t`treturn "ERROR";
`t`t`t}
`t`t}

`t`tprivate static decimal _LastLatitude = 0;
`t`tprivate static decimal GetLatitude(string status)
`t`t{
`t`t`tRandom rand = new();
`t`t`tif (_LastLatitude == 0)
`t`t`t{
`t`t`t`t_LastLatitude = (decimal)(rand.NextDouble() * 180 - 90);
`t`t`t}

`t`t`tif (status == "ERROR" && _LastPropError == EProps.latitude)
`t`t`t{
`t`t`t`tGetNextPropError();
`t`t`t`treturn Math.Round(100 + (decimal)(rand.NextDouble() * 10), 6);
`t`t`t}

`t`t`treturn Math.Round(_LastLatitude, 6);
`t`t}

`t`tprivate static decimal _LastLongitude = 0;
`t`tprivate static decimal GetLongitude(string status)
`t`t{
`t`t`tRandom rand = new();
`t`t`tif (_LastLongitude == 0)
`t`t`t{
`t`t`t`t_LastLongitude = (decimal)(rand.NextDouble() * 360 - 180);
`t`t`t}

`t`t`tif (status == "ERROR" && _LastPropError == EProps.longitude)
`t`t`t{
`t`t`t`tGetNextPropError();
`t`t`t`treturn Math.Round(200 + (decimal)(rand.NextDouble() * 10), 6);
`t`t`t}

`t`t`treturn Math.Round(_LastLongitude, 6);
`t`t}

`t`tprivate static decimal _LastBatteryLevel = 0;
`t`tprivate static decimal GetBatteryLevel(string status)
`t`t{
`t`t`tRandom rand = new();
`t`t`tif (_LastBatteryLevel == 0)
`t`t`t{
`t`t`t`t_LastBatteryLevel = (decimal)rand.NextDouble();
`t`t`t}
`t`t`telse
`t`t`t{
`t`t`t`tdecimal variation = (decimal)(rand.NextDouble() * 0.02 - 0.01);
`t`t`t`t_LastBatteryLevel += variation;
`t`t`t`tif (_LastBatteryLevel < 0) _LastBatteryLevel = 0;
`t`t`t`tif (_LastBatteryLevel > 1) _LastBatteryLevel = 1;
`t`t`t}

`t`t`tif (status == "ERROR" && _LastPropError == EProps.longitude)
`t`t`t{
`t`t`t`tGetNextPropError();
`t`t`t`treturn Math.Round(1.5m + (decimal)(rand.NextDouble() * 0.5), 2);
`t`t`t}

`t`t`treturn Math.Round(_LastBatteryLevel, 2);
`t`t}

`t`tprivate static decimal _LastHumidity = 0;
`t`tprivate static decimal GetHumidity(string status)
`t`t{
`t`t`tRandom rand = new();
`t`t`tif (_LastHumidity == 0)
`t`t`t{
`t`t`t`t_LastHumidity = rand.Next(10, 90);
`t`t`t}
`t`t`telse
`t`t`t{
`t`t`t`tdecimal variation = (decimal)(rand.NextDouble() * 2 - 1);
`t`t`t`t_LastHumidity += variation;
`t`t`t}

`t`t`tif (status == "ERROR" && _LastPropError == EProps.humidity)
`t`t`t{
`t`t`t`tGetNextPropError();
`t`t`t`treturn Math.Round(150 + (decimal)(rand.NextDouble() * 10), 2);
`t`t`t}

`t`t`treturn Math.Round(_LastHumidity, 2);
`t`t}

`t`tprivate static decimal _LastTemp = 0;
`t`tprivate static decimal GetTemperature(string status)
`t`t{
`t`t`tRandom rand = new();
`t`t`tif (_LastTemp == 0)
`t`t`t{
`t`t`t`t_LastTemp = rand.Next(-10, 120);
`t`t`t}
`t`t`telse
`t`t`t{
`t`t`t`tdecimal variation = (decimal)(rand.NextDouble() - 0.5);
`t`t`t`t_LastTemp += variation;
`t`t`t}

`t`t`tif (status == "ERROR" && _LastPropError == EProps.temperature)
`t`t`t{
`t`t`t`tGetNextPropError();
`t`t`t`treturn Math.Round(200 + (decimal)(rand.NextDouble() * 50), 2);
`t`t`t}

`t`t`treturn Math.Round(_LastTemp, 2);
`t`t}
`t}
}

