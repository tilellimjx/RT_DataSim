using System;

namespace RealTimeDataSimulator
{
`tinternal class RTData
`t{
`t`tpublic string? device_id { get; set; }
`t`tpublic DateTime timestamp { get; set; }
`t`tpublic decimal temperature { get; set; }
`t`tpublic decimal humidity { get; set; }
`t`tpublic decimal battery_level { get; set; }
`t`tpublic Location? location { get; set; }
`t`tpublic string? status { get; set; }
`t}

`tinternal class Location
`t{
`t`tpublic decimal latitude { get; set; }
`t`tpublic decimal longitude { get; set; }
`t}
}

