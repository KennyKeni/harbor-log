use crate::config::Config;
use crate::patching::PatchTracker;
use crate::status::StatusWriter;
use crate::transport::EventSender;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};
use std::thread;
use std::time::Duration;

pub fn run(
    config: &Config,
    sender: &EventSender,
    status: &mut StatusWriter,
    patches: &mut PatchTracker,
) -> Result<(), String> {
    let mut state = TerminusState::default();

    loop {
        let paths = trajectory_paths(&config.log_root)?;
        for path in paths {
            let payload = match fs::read_to_string(&path) {
                Ok(raw) => serde_json::from_str::<Value>(&raw).map_err(|err| err.to_string())?,
                Err(err) => return Err(err.to_string()),
            };

            let file_key = path
                .file_name()
                .and_then(|value| value.to_str())
                .unwrap_or("trajectory.json")
                .to_string();
            let steps = payload
                .get("steps")
                .and_then(|value| value.as_array())
                .cloned()
                .unwrap_or_default();
            let emitted = state.emitted_steps.entry(file_key).or_insert(0usize);
            if steps.len() < *emitted {
                *emitted = steps.len();
            }

            if !state.session_started && !steps.is_empty() {
                sender.send(
                    "agent.session_started",
                    json!({
                        "session_id": payload.get("session_id"),
                        "model_name": payload
                            .get("agent")
                            .and_then(|value| value.get("model_name")),
                    }),
                )?;
                status.event_sent();
                state.session_started = true;
            }

            for step in steps.iter().skip(*emitted) {
                if step.get("source").and_then(|value| value.as_str()) != Some("agent") {
                    continue;
                }

                if let Some(reasoning) = step
                    .get("reasoning_content")
                    .and_then(|value| value.as_str())
                    .filter(|value| !value.is_empty())
                {
                    sender.send("agent.reasoning", json!({ "text": reasoning }))?;
                    status.event_sent();
                }

                let tool_calls = step
                    .get("tool_calls")
                    .and_then(|value| value.as_array())
                    .cloned()
                    .unwrap_or_default();
                if !tool_calls.is_empty() {
                    for tool_call in &tool_calls {
                        sender.send(
                            "agent.tool_call",
                            json!({
                                "step_id": step.get("step_id"),
                                "timestamp": step.get("timestamp"),
                                "call_id": tool_call.get("tool_call_id"),
                                "tool_name": tool_call.get("function_name"),
                                "arguments": tool_call.get("arguments"),
                            }),
                        )?;
                        status.event_sent();
                    }
                    let tool_name = tool_calls
                        .first()
                        .and_then(|value| value.get("function_name"))
                        .and_then(|value| value.as_str())
                        .unwrap_or("tool");
                    let call_id = tool_calls
                        .first()
                        .and_then(|value| value.get("tool_call_id"))
                        .and_then(|value| value.as_str());

                    for observation in step
                        .get("observation")
                        .and_then(|value| value.get("results"))
                        .and_then(|value| value.as_array())
                        .cloned()
                        .unwrap_or_default()
                    {
                        sender.send(
                            "agent.tool_result",
                            json!({
                                "step_id": step.get("step_id"),
                                "timestamp": step.get("timestamp"),
                                "call_id": observation.get("source_call_id"),
                                "content": observation.get("content"),
                            }),
                        )?;
                        status.event_sent();
                    }

                    if patches.enabled() {
                        if let Some(patch) = patches.snapshot(tool_name, call_id) {
                            sender.send("agent.file_patch", patch)?;
                            status.patch_sent();
                        }
                    }
                } else if let Some(message) = step.get("message").and_then(|value| value.as_str()) {
                    if !message.is_empty() {
                        sender.send(
                            "agent.message",
                            json!({
                                "step_id": step.get("step_id"),
                                "timestamp": step.get("timestamp"),
                                "text": message,
                            }),
                        )?;
                        status.event_sent();
                    }
                }
            }

            *emitted = steps.len();
        }

        thread::sleep(Duration::from_millis(500));
    }
}

#[derive(Default)]
struct TerminusState {
    session_started: bool,
    emitted_steps: HashMap<String, usize>,
}

fn trajectory_paths(root: &Path) -> Result<Vec<PathBuf>, String> {
    let mut paths = Vec::new();
    let main = root.join("trajectory.json");
    if main.exists() {
        paths.push(main);
    }

    let mut continuations: Vec<PathBuf> = fs::read_dir(root)
        .map_err(|err| err.to_string())?
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| {
            path.file_name()
                .and_then(|value| value.to_str())
                .map(|name| name.starts_with("trajectory.cont-") && name.ends_with(".json"))
                .unwrap_or(false)
        })
        .collect();
    continuations.sort_by_key(|path| {
        path.file_name()
            .and_then(|value| value.to_str())
            .and_then(|name| {
                name.trim_start_matches("trajectory.cont-")
                    .trim_end_matches(".json")
                    .parse::<u32>()
                    .ok()
            })
            .unwrap_or(0)
    });
    paths.extend(continuations);
    Ok(paths)
}
