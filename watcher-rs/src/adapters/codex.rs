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

pub fn run(
    config: &Config,
    sender: &EventSender,
    status: &mut StatusWriter,
    patches: &mut PatchTracker,
) -> Result<(), String> {
    let path = config.codex_log_path();
    if !wait_for_path(&path, FILE_WAIT_TIMEOUT) {
        return Err(format!("Codex log not found: {}", path.display()));
    }

    let mut state = TailState::default();
    let mut adapter = CodexAdapter::default();

    loop {
        for line in state.read_new_lines(&path)? {
            let events = adapter.parse_line(&line);
            for parsed in events {
                sender.send(parsed.event_type, parsed.data.clone())?;
                status.event_sent();
                if parsed.event_type == "agent.tool_result" && patches.enabled() {
                    if let Some(call_id) = parsed.data.get("call_id").and_then(|value| value.as_str()) {
                        let tool_name = adapter
                            .pending_tools
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

#[derive(Default)]
struct CodexAdapter {
    session_started: bool,
    session_id: Option<String>,
    model_name: Option<String>,
    pending_reasoning: Option<String>,
    pending_tools: HashMap<String, String>,
}

struct ParsedEvent {
    event_type: &'static str,
    data: Value,
}

impl CodexAdapter {
    fn parse_line(&mut self, line: &str) -> Vec<ParsedEvent> {
        let mut parsed_events = Vec::new();
        let Ok(event) = serde_json::from_str::<Value>(line) else {
            return parsed_events;
        };

        let event_type = event.get("type").and_then(|value| value.as_str()).unwrap_or("");
        match event_type {
            "session_meta" => {
                self.session_id = event
                    .get("payload")
                    .and_then(|value| value.get("id"))
                    .and_then(|value| value.as_str())
                    .map(str::to_string);
                if !self.session_started {
                    parsed_events.push(self.session_started_event());
                    self.session_started = true;
                }
            }
            "turn_context" => {
                self.model_name = event
                    .get("payload")
                    .and_then(|value| value.get("model"))
                    .and_then(|value| value.as_str())
                    .map(str::to_string);
            }
            "response_item" => {
                if !self.session_started {
                    parsed_events.push(self.session_started_event());
                    self.session_started = true;
                }
                let payload = event.get("payload").cloned().unwrap_or(Value::Null);
                let payload_type = payload.get("type").and_then(|value| value.as_str()).unwrap_or("");
                match payload_type {
                    "reasoning" => {
                        self.pending_reasoning = payload
                            .get("summary")
                            .and_then(|value| value.as_array())
                            .map(|items| {
                                items
                                    .iter()
                                    .filter_map(|item| item.as_str())
                                    .collect::<Vec<_>>()
                                    .join("\n")
                            })
                            .filter(|value| !value.is_empty());
                    }
                    "message" => {
                        if let Some(reasoning) = self.pending_reasoning.take() {
                            parsed_events.push(ParsedEvent {
                                event_type: "agent.reasoning",
                                data: json!({ "text": reasoning }),
                            });
                        }
                        let text = payload
                            .get("content")
                            .and_then(|value| value.as_array())
                            .map(|items| extract_message_text(items))
                            .unwrap_or_default();
                        parsed_events.push(ParsedEvent {
                            event_type: "agent.message",
                            data: json!({ "text": text }),
                        });
                    }
                    "function_call" | "custom_tool_call" => {
                        let call_id = payload
                            .get("call_id")
                            .and_then(|value| value.as_str())
                            .unwrap_or("");
                        let raw_arguments = payload
                            .get(if payload_type == "function_call" {
                                "arguments"
                            } else {
                                "input"
                            })
                            .cloned()
                            .unwrap_or(Value::Null);
                        let arguments = parse_arguments(&raw_arguments);
                        let tool_name = payload
                            .get("name")
                            .and_then(|value| value.as_str())
                            .unwrap_or("")
                            .to_string();
                        self.pending_tools
                            .insert(call_id.to_string(), tool_name.clone());
                        if let Some(reasoning) = self.pending_reasoning.take() {
                            parsed_events.push(ParsedEvent {
                                event_type: "agent.reasoning",
                                data: json!({ "text": reasoning }),
                            });
                        }
                        parsed_events.push(ParsedEvent {
                            event_type: "agent.tool_call",
                            data: json!({
                                "call_id": call_id,
                                "tool_name": tool_name,
                                "arguments": arguments,
                            }),
                        });
                    }
                    "function_call_output" | "custom_tool_call_output" => {
                        let content = parse_output_blob(payload.get("output"));
                        parsed_events.push(ParsedEvent {
                            event_type: "agent.tool_result",
                            data: json!({
                                "call_id": payload.get("call_id"),
                                "content": content,
                            }),
                        });
                    }
                    _ => {}
                }
            }
            _ => {}
        }

        parsed_events
    }

    fn session_started_event(&self) -> ParsedEvent {
        ParsedEvent {
            event_type: "agent.session_started",
            data: json!({
                "session_id": self.session_id,
                "model_name": self.model_name,
            }),
        }
    }
}

fn extract_message_text(items: &[Value]) -> String {
    items
        .iter()
        .filter_map(|item| item.get("text").and_then(|value| value.as_str()))
        .collect::<Vec<_>>()
        .join("")
}

fn parse_arguments(raw: &Value) -> Value {
    match raw {
        Value::String(text) => serde_json::from_str(text).unwrap_or_else(|_| json!({ "input": text })),
        Value::Null => json!({}),
        other => other.clone(),
    }
}

fn parse_output_blob(raw: Option<&Value>) -> Value {
    let Some(raw) = raw else {
        return Value::Null;
    };
    match raw {
        Value::String(text) => match serde_json::from_str::<Value>(text) {
            Ok(value) => value
                .get("output")
                .cloned()
                .unwrap_or_else(|| value.clone()),
            Err(_) => Value::String(text.clone()),
        },
        other => other.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::{parse_arguments, parse_output_blob};
    use serde_json::json;

    #[test]
    fn parse_arguments_decodes_json_strings() {
        assert_eq!(parse_arguments(&json!("{\"cmd\":\"ls\"}")), json!({"cmd": "ls"}));
    }

    #[test]
    fn parse_output_blob_prefers_nested_output() {
        assert_eq!(
            parse_output_blob(Some(&json!("{\"output\":\"done\",\"metadata\":{\"x\":1}}"))),
            json!("done"),
        );
    }
}
