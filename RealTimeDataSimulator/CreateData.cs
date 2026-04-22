using System;
using System.IO;
using System.Text.Json;

namespace RealTimeDataSimulator
{
	internal class CreateData
	{
		private enum EProps
		{
			temperature,
			humidity,
			battery_level,
			longitude,
			latitude,
		}

		internal static void GenerateData()
		{
			if (!Directory.Exists($@"C:\Temp\data"))
			{
				Directory.CreateDirectory($@"C:\Temp\data");
			}

			if (File.Exists($@"C:\Temp\data\CorruptionLog.txt"))
			{
				File.Delete($@"C:\Temp\data\CorruptionLog.txt");
			}

			for (int fileIndex = 1; fileIndex <= 250; fileIndex++)
			{
				var f = File.Create($@"C:\Temp\data\datafile_{fileIndex}.txt");
				using StreamWriter writer = new(f);
				for (int second = 0; second < 7200; second++)
				{
					string status = CreateStatus();
					RTData data = new()
					{
						device_id = $"Sensor_{fileIndex}",
						timestamp = DateTime.UtcNow,
						temperature = GetTemperature(status),
						humidity = GetHumidity(status),
						battery_level = GetBatteryLevel(status),
						location = new()
						{
							latitude = GetLatitude(status),
							longitude = GetLongitude(status)
						},
						status = status
					};

					IntroducePossibleCorruption(ref data);

					string line = JsonSerializer.Serialize(data);
					writer.WriteLine(line);
				}

				writer.Flush();
				writer.Close();
				f.Close();

				var fw = File.Open($@"C:\Temp\data\CorruptionLog.txt", FileMode.OpenOrCreate, FileAccess.Write);
				fw.Seek(0, SeekOrigin.End);
				using StreamWriter sw = new(fw);
				sw.WriteLine($"Number of corrupted entries in file {fileIndex}: {_corruptionCounter}");
				sw.Flush();
				sw.Close();
				fw.Close();

				_LastTemp = 0;
				_LastHumidity = 0;
				_LastBatteryLevel = 0;
				_LastLongitude = 0;
				_LastLatitude = 0;
				_corruptionCounter = 0;
			}
		}

		private static int _corruptionCounter = 0;
		private static void IntroducePossibleCorruption(ref RTData data)
		{
			Random rand = new();
			int value = rand.Next(1, 1001);
			if (value == 1)
			{
				data.temperature = decimal.MinValue;
			}
			else if (value == 2)
			{
				data.humidity = decimal.MinValue;
			}
			else if (value == 3)
			{
				data.battery_level = decimal.MinValue;
			}
			else if (value == 4)
			{
				data.location.latitude = decimal.MinValue;
			}
			else if (value == 5)
			{
				data.location.longitude = decimal.MinValue;
			}

			if (value <= 5)
			{
				_corruptionCounter++;
			}
		}

		private static EProps _LastPropError = EProps.temperature;
		private static void GetNextPropError()
		{
			if (_LastPropError == EProps.latitude)
			{
				_LastPropError = EProps.temperature;
			}
			else
			{
				_LastPropError++;
			}
		}

		private static string CreateStatus()
		{
			Random rand = new();
			int value = rand.Next(1, 101);
			if (value <= 92)
			{
				return "OK";
			}
			else if (value <= 98)
			{
				return "WARN";
			}
			else
			{
				return "ERROR";
			}
		}

		private static decimal _LastLatitude = 0;
		private static decimal GetLatitude(string status)
		{
			Random rand = new();
			if (_LastLatitude == 0)
			{
				_LastLatitude = (decimal)(rand.NextDouble() * 180 - 90);
			}

			if (status == "ERROR" && _LastPropError == EProps.latitude)
			{
				GetNextPropError();
				return Math.Round(100 + (decimal)(rand.NextDouble() * 10), 6);
			}

			return Math.Round(_LastLatitude, 6);
		}

		private static decimal _LastLongitude = 0;
		private static decimal GetLongitude(string status)
		{
			Random rand = new();
			if (_LastLongitude == 0)
			{
				_LastLongitude = (decimal)(rand.NextDouble() * 360 - 180);
			}

			if (status == "ERROR" && _LastPropError == EProps.longitude)
			{
				GetNextPropError();
				return Math.Round(200 + (decimal)(rand.NextDouble() * 10), 6);
			}

			return Math.Round(_LastLongitude, 6);
		}

		private static decimal _LastBatteryLevel = 0;
		private static decimal GetBatteryLevel(string status)
		{
			Random rand = new();
			if (_LastBatteryLevel == 0)
			{
				_LastBatteryLevel = (decimal)rand.NextDouble();
			}
			else
			{
				decimal variation = (decimal)(rand.NextDouble() * 0.02 - 0.01);
				_LastBatteryLevel += variation;
				if (_LastBatteryLevel < 0) _LastBatteryLevel = 0;
				if (_LastBatteryLevel > 1) _LastBatteryLevel = 1;
			}

			if (status == "ERROR" && _LastPropError == EProps.longitude)
			{
				GetNextPropError();
				return Math.Round(1.5m + (decimal)(rand.NextDouble() * 0.5), 2);
			}

			return Math.Round(_LastBatteryLevel, 2);
		}

		private static decimal _LastHumidity = 0;
		private static decimal GetHumidity(string status)
		{
			Random rand = new();
			if (_LastHumidity == 0)
			{
				_LastHumidity = rand.Next(10, 90);
			}
			else
			{
				decimal variation = (decimal)(rand.NextDouble() * 2 - 1);
				_LastHumidity += variation;
			}

			if (status == "ERROR" && _LastPropError == EProps.humidity)
			{
				GetNextPropError();
				return Math.Round(150 + (decimal)(rand.NextDouble() * 10), 2);
			}

			return Math.Round(_LastHumidity, 2);
		}

		private static decimal _LastTemp = 0;
		private static decimal GetTemperature(string status)
		{
			Random rand = new();
			if (_LastTemp == 0)
			{
				_LastTemp = rand.Next(-10, 120);
			}
			else
			{
				decimal variation = (decimal)(rand.NextDouble() - 0.5);
				_LastTemp += variation;
			}

			if (status == "ERROR" && _LastPropError == EProps.temperature)
			{
				GetNextPropError();
				return Math.Round(200 + (decimal)(rand.NextDouble() * 50), 2);
			}

			return Math.Round(_LastTemp, 2);
		}
	}
}


