use crate::config::Config;
use crate::patching::PatchTracker;
use crate::status::StatusWriter;
use crate::tail::{wait_for_path, TailState};
use crate::transport::EventSender;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::thread;
use std::time::Duration;

const FILE_WAIT_TIMEOUT: Duration = Duration::from_secs(600);

fn truncate(input: &str, max: usize) -> String {
    if input.chars().count() <= max {
        return input.to_string();
    }
    input.chars().take(max).collect::<String>() + "..."
}

pub fn run(
    config: &Config,
    sender: &EventSender,
    status: &mut StatusWriter,
    patches: &mut PatchTracker,
) -> Result<(), String> {
    let path = config.claude_log_path();
    if !wait_for_path(&path, FILE_WAIT_TIMEOUT) {
        return Err(format!("Claude log not found: {}", path.display()));
    }

    let mut state = TailState::default();
    let mut pending_tools: HashMap<String, String> = HashMap::new();
    let mut session_started = false;

    loop {
        for line in state.read_new_lines(&path)? {
            if let Some(event) = parse_event(&line) {
                if event.event_type == "agent.session_started" {
                    session_started = true;
                } else if !session_started {
                    sender.send(
                        "agent.session_started",
                        json!({
                            "session_id": Value::Null,
                            "model_name": Value::Null,
                        }),
                    )?;
                    status.event_sent();
                    session_started = true;
                }

                sender.send(event.event_type, event.data.clone())?;
                if event.event_type == "agent.file_patch" {
                    status.patch_sent();
                } else {
                    status.event_sent();
                }

                if event.event_type == "agent.tool_call" {
                    if let (Some(call_id), Some(tool_name)) = (
                        event.data.get("call_id").and_then(|value| value.as_str()),
                        event.data.get("tool_name").and_then(|value| value.as_str()),
                    ) {
                        pending_tools.insert(call_id.to_string(), tool_name.to_string());
                    }
                }

                if event.event_type == "agent.tool_result" && patches.enabled() {
                    if let Some(call_id) = event.data.get("call_id").and_then(|value| value.as_str()) {
                        let tool_name = pending_tools
                            .remove(call_id)
                            .unwrap_or_else(|| "unknown".to_string());
                        if let Some(patch) = patches.snapshot(&tool_name, Some(call_id)) {
                            sender.send("agent.file_patch", patch)?;
                            status.patch_sent();
                        }
                    }
                }
            }
        }
        thread::sleep(Duration::from_millis(500));
    }
}

struct ParsedEvent {
    event_type: &'static str,
    data: Value,
}

fn parse_event(line: &str) -> Option<ParsedEvent> {
    let event: Value = serde_json::from_str(line).ok()?;
    let event_type = event.get("type")?.as_str()?;

    match event_type {
        "system" => {
            if event.get("subtype")?.as_str()? != "init" {
                return None;
            }
            Some(ParsedEvent {
                event_type: "agent.session_started",
                data: json!({
                    "session_id": event.get("session_id"),
                    "model_name": event.get("model"),
                    "tools_count": event
                        .get("tools")
                        .and_then(|value| value.as_array())
                        .map(|items| items.len())
                        .unwrap_or(0),
                }),
            })
        }
        "assistant" => {
            let block = event
                .get("message")?
                .get("content")?
                .as_array()?
                .first()?
                .as_object()?;
            match block.get("type")?.as_str()? {
                "tool_use" => Some(ParsedEvent {
                    event_type: "agent.tool_call",
                    data: json!({
                        "tool_name": block.get("name"),
                        "call_id": block.get("id"),
                        "arguments": block.get("input"),
                    }),
                }),
                "text" => Some(ParsedEvent {
                    event_type: "agent.message",
                    data: json!({
                        "text": truncate(block.get("text").and_then(|value| value.as_str()).unwrap_or(""), 1200),
                    }),
                }),
                "thinking" | "reasoning" | "analysis" => Some(ParsedEvent {
                    event_type: "agent.reasoning",
                    data: json!({
                        "text": truncate(
                            block
                                .get("thinking")
                                .or_else(|| block.get("text"))
                                .and_then(|value| value.as_str())
                                .unwrap_or(""),
                            1200,
                        ),
                    }),
                }),
                _ => None,
            }
        }
        "user" => {
            let block = event
                .get("message")?
                .get("content")?
                .as_array()?
                .first()?
                .as_object()?;
            if block.get("type")?.as_str()? != "tool_result" {
                return None;
            }
            let result = event.get("tool_use_result");
            Some(ParsedEvent {
                event_type: "agent.tool_result",
                data: json!({
                    "call_id": block.get("tool_use_id"),
                    "content": {
                        "stdout": truncate(result.and_then(|value| value.get("stdout")).and_then(|value| value.as_str()).unwrap_or(""), 2000),
                        "stderr": truncate(result.and_then(|value| value.get("stderr")).and_then(|value| value.as_str()).unwrap_or(""), 2000),
                        "is_error": block.get("is_error").and_then(|value| value.as_bool()).unwrap_or(false),
                    },
                }),
            })
        }
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::parse_event;

    #[test]
    fn parses_tool_use_events() {
        let line = r#"{"type":"assistant","message":{"content":[{"type":"tool_use","name":"bash","id":"call-1","input":{"cmd":"ls"}}]}}"#;
        let parsed = parse_event(line).expect("expected tool call");
        assert_eq!(parsed.event_type, "agent.tool_call");
        assert_eq!(parsed.data.get("tool_name").and_then(|value| value.as_str()), Some("bash"));
    }
}
