# harbor-log

`harbor-log` streams Harbor trial lifecycle events and live agent activity to an HTTP endpoint.

The repository is named `harbor-log`. The current Python package and CLI entrypoint are still named `harbor-stream` / `harbor_stream`.

## What it does

- Runs a Harbor `JobConfig` through Harbor's Python API instead of wrapping `harbor run`
- Emits host-side trial lifecycle events such as `trial.started`, `trial.environment_started`, and `trial.finished`
- Streams helper-side agent events including `agent.message`, `agent.tool_call`, `agent.tool_result`, `agent.raw_line`, and `agent.final.summary`
- Posts JSON event envelopes to a configurable HTTP endpoint

Each event includes common metadata such as `schema_version`, `event_id`, `timestamp`, `job_name`, `trial_id`, `task_name`, `agent_name`, `environment_type`, `event_type`, and `data`.

## Requirements

- Python 3.12+
- Harbor installed in the same environment

## Install

```bash
python -m pip install .
```

## Usage

```bash
harbor-stream run \
  --config job.yaml \
  --stream-url https://collector.example/events
```

Supported config formats:

- `.yaml`
- `.yml`
- `.json`

Optional flags:

- `--stream-token` to send a bearer token with each request
- `--job-name` to override `job_name` before launch
- `--jobs-dir` to override `jobs_dir` before launch

## Docker note

When Harbor runs with a Docker environment, a loopback `--stream-url` such as `http://127.0.0.1:8080/events` is rewritten for the helper process to use `host.docker.internal` by default. Override that hostname with `HARBOR_STREAM_DOCKER_HOST` if needed.
