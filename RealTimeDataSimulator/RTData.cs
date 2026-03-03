namespace RealTimeDataSimulator
{
    internal class RTData
    {
        public string device_id { get; set; }
        public DateTime timestamp { get; set; }
        public decimal temperature { get; set; }
        public decimal humidity { get; set; }
        public decimal battery_level { get; set; }
        public Location location { get; set; }
        public string status { get; set; }
    }

    internal class Location
    {
        public decimal latitude { get; set; }
        public decimal longitude { get; set; }
    }
}
