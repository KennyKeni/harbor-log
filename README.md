# harbor-stream

Stream Harbor trial lifecycle events and selected live agent events to an HTTP endpoint.

## Usage

```bash
harbor-stream run \
  --config job.yaml \
  --stream-url https://collector.example/events
```

`--config` is a Harbor `JobConfig` file. `harbor-stream` validates and runs it through Harbor's Python API rather than wrapping `harbor run`.
