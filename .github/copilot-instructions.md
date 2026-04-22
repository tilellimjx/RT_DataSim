Copilot instructions for RT_DataSim

Quick commands
- Build (project):
  dotnet build .\RealTimeDataSimulator\RealTimeDataSimulator.csproj
- Run (create data):
  dotnet run --project .\RealTimeDataSimulator\RealTimeDataSimulator.csproj -- create
- Run (send data):
  dotnet run --project .\RealTimeDataSimulator\RealTimeDataSimulator.csproj -- send
- Publish (release):
  dotnet publish -c Release -o ./publish --project .\RealTimeDataSimulator\RealTimeDataSimulator.csproj
- Python Lambda (local deps):
  pip install -r aws\gatewayapi_requirements.txt
- CodeBuild: aws/gatewayapi_buildspec.yml present (used by pipeline/CodeBuild).

Tests & linters
- There are no test projects or explicit linting configs in this repo. Use dotnet test if/when a test project is added. For C# style/linting, dotnet format and Roslyn analyzers may be added later.

High-level architecture (big picture)
- Core C# simulator (RealTimeDataSimulator):
  - Program.cs: CLI entrypoint with two modes: "create" and "send".
  - CreateData.GenerateData(): creates 250 files under C:\Temp\data (datafile_1..datafile_250.txt). Each file contains one JSON line per second for 2 hours and a CorruptionLog.txt recording corrupted entries.
  - SendData.StartSending(): reads each file and sends each JSON line to a REST endpoint (Post to https://pqxu4yuom8.execute-api.us-east-2.amazonaws.com/version1) at a 1-second cadence. It launches the 250 file-senders in parallel.
  - RTData.cs: in-memory schema for the telemetry JSON (device_id, timestamp, temperature, humidity, battery_level, location, status).
- AWS helper (aws/gatewayapi.py): a small Lambda-style function that writes incoming JSON to S3 buckets: rt-json-data (normal) and rt-json-error-data (on JSON conversion error). The repository includes a CodeBuild buildspec (aws/gatewayapi_buildspec.yml).

Key repo-specific conventions & gotchas
- Uses absolute path C:\Temp\data for generated files and logs (CorruptionLog.txt, SendErrorsLog.txt). Running create mode will create the directory and files there.
- File and naming patterns:
  - Data files: datafile_<index>.txt (1..250)
  - Device IDs: Sensor_<index>
  - Logs: CorruptionLog.txt (per run), SendErrorsLog.txt (send-mode failures)
- Program interface: single-argument CLI: create | send. If no arg or unknown arg, the program prints usage.
- Concurrency and networking:
  - SendData spawns 250 tasks and uses a new HttpClient per SendToEndpoint call; this is a heavy concurrency pattern and may cause socket exhaustion in different environments. When updating network code, prefer reusing HttpClient or throttling concurrency.
  - Send cadence is enforced by Thread.Sleep to approximate one-second intervals per record; changing timing must respect that logic.
- Data corruption simulation: CreateData introduces deterministic-patterned and random corruptions (decimal.MinValue used to mark corrupted numeric fields). Do not change the corruption sentinel without updating consumers.
- Remove empty directories before committing: Git does not track empty directories. Delete any empty folders before check-in or add a placeholder file (for example, .gitkeep) when a directory must be preserved.

Files to check first when changing behavior
- RealTimeDataSimulator\CreateData.cs — file generation, corruption rules, write paths
- RealTimeDataSimulator\SendData.cs — sending logic, concurrency, endpoint URL
- aws\gatewayapi.py and aws\gatewayapi_buildspec.yml — Lambda ingestion and CodeBuild artifact steps

AI assistant notes for copilot sessions
- When editing SendData, search for HttpClient usage and the hardcoded endpoint (https://pqxu4yuom8.execute-api.us-east-2.amazonaws.com/version1). Consider reuse of HttpClient or adding configurable endpoint via args or config files.
- Paths are absolute by design (C:\Temp\data). If making data location configurable, update both CreateData and SendData.
- No test projects detected — propose adding a test project (xUnit/NUnit) if requested; include guidance on how to run single tests (dotnet test --filter FullyQualifiedName=...) when tests are added.
- No other AI assistant configs found (CLAUDE.md, .cursorrules, AGENTS.md, .windsurfrules, CONVENTIONS.md, etc.).
- When performing code reviews, convert leading indentation from spaces to tabs and prefer using directives ("using ...;") over fully-qualified type names in C# files.

If existing .github/copilot-instructions.md existed, propose: keep command examples, add explicit guidance for HttpClient reuse and concurrency safety, and document C:\Temp\data dependency.

---
Summary: concise build/run commands, high-level architecture, and repo-specific conventions created. Would you like adjustments or coverage for additional areas (CI, deployment, tests)?
