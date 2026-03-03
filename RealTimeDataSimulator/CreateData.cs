
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

            // there needs to be 250 files created. each file has one line of data per second for two hours
            for (int fileIndex = 1; fileIndex <= 250; fileIndex++)
            {
                var f = File.Create(@$"C:\Temp\data\datafile_{fileIndex}.txt");
                using StreamWriter writer = new(f);
                for (int second = 0; second < 7200; second++)
                {
                    string status = CreateStatus();
                    // create one line of data
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

                    // introduce a possible corruption in the data line with 1% chance
                    IntroducePossibleCorruption(ref data);

                    // convert to json
                    string line = System.Text.Json.JsonSerializer.Serialize(data);
                    writer.WriteLine(line);
                }

                writer.Flush();
                writer.Close();

                // close the file
                f.Close();

                // update a file to keep track of all the corruptions in each file
                var fw = File.Open($@"C:\Temp\data\CorruptionLog.txt", FileMode.OpenOrCreate, FileAccess.Write);
                fw.Seek(0, SeekOrigin.End);
                using StreamWriter sw = new(fw);
                sw.WriteLine($"Number of corrupted entries in file {fileIndex}: {_corruptionCounter}");
                sw.Flush();
                sw.Close();
                fw.Close();

                // reset last values for next file
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
            // introduce a 0.1% chance of corruption regardless of status
            Random rand = new();
            int value = rand.Next(1, 1001);
            if (value == 1)
            {
                // corrupt the data by setting temperature to null
                data.temperature = decimal.MinValue;
            }
            else if (value == 2)
            {
                // corrupt the data by setting humidity to null
                data.humidity = decimal.MinValue;
            }
            else if (value == 3)
            {
                // corrupt the data by setting battery_level to null
                data.battery_level = decimal.MinValue;
            }
            else if (value == 4)
            {
                // corrupt the data by setting latitude to null
                data.location.latitude = decimal.MinValue;
            }
            else if (value == 5)
            {
                // corrupt the data by setting longitude to null
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
            // create a weighted random status with 92% "OK", 6% "WARN", 2% "ERROR"
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
                // pick a random latitude between -90 and 90
                _LastLatitude = (decimal)(rand.NextDouble() * 180 - 90);
            }

            if (status == "ERROR" && _LastPropError == EProps.latitude)
            {
                GetNextPropError();
                //return a latitude outside valid range to simulate error
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
                // pick a random longitude between -180 and 180
                _LastLongitude = (decimal)(rand.NextDouble() * 360 - 180);
            }

            if (status == "ERROR" && _LastPropError == EProps.longitude)
            {
                GetNextPropError();
                //return a longitude outside valid range to simulate error
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
                // pick a random battery level between 0 and 1
                _LastBatteryLevel = (decimal)rand.NextDouble();
            }
            else
            {
                // vary the battery level by -0.01 to +0.01
                decimal variation = (decimal)(rand.NextDouble() * 0.02 - 0.01);
                _LastBatteryLevel += variation;
                if (_LastBatteryLevel < 0) _LastBatteryLevel = 0;
                if (_LastBatteryLevel > 1) _LastBatteryLevel = 1;
            }

            if (status == "ERROR" && _LastPropError == EProps.longitude)
            {
                GetNextPropError();
                //return a battery level outside valid range to simulate error
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
                // pick a random humidity between 10 and 90
                _LastHumidity = rand.Next(10, 90);
            }
            else
            {
                // vary the humidity by -1 to +1 percent
                decimal variation = (decimal)(rand.NextDouble() * 2 - 1);
                _LastHumidity += variation;
            }

            if (status == "ERROR" && _LastPropError == EProps.humidity)
            {
                GetNextPropError();
                //return a humidity outside valid range to simulate error
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
                // pick a random temp between -10 and 120
                _LastTemp = rand.Next(-10, 120);
            }
            else
            {
                // vary the temp by -0.5 to +0.5 degrees
                decimal variation = (decimal)(rand.NextDouble() - 0.5);
                _LastTemp += variation;
            }

            if (status == "ERROR" && _LastPropError == EProps.temperature)
            {
                GetNextPropError();
                //return a temperature outside valid range to simulate error
                return Math.Round(200 + (decimal)(rand.NextDouble() * 50), 2);
            }

            return Math.Round(_LastTemp, 2);
        }
    }
}
