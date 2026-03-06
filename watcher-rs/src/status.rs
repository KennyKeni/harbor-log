use crate::config::Mode;
use chrono::Utc;
use serde::Serialize;
use std::fs;
use std::path::PathBuf;

#[derive(Default, Serialize)]
pub struct StatusState {
    mode: String,
    started_at: String,
    events_emitted: u64,
    patches_emitted: u64,
    last_event_at: Option<String>,
    last_error: Option<String>,
    completed: bool,
    completed_at: Option<String>,
}

pub struct StatusWriter {
    path: PathBuf,
    state: StatusState,
}

impl StatusWriter {
    pub fn new(path: PathBuf, mode: &Mode) -> Self {
        let mode_name = match mode {
            Mode::Claude => "claude",
            Mode::Codex => "codex",
            Mode::Terminus2 => "terminus2",
            Mode::Raw => "raw",
        };
        let mut writer = Self {
            path,
            state: StatusState {
                mode: mode_name.to_string(),
                started_at: Utc::now().to_rfc3339(),
                ..StatusState::default()
            },
        };
        writer.persist();
        writer
    }

    pub fn event_sent(&mut self) {
        self.state.events_emitted += 1;
        self.state.last_event_at = Some(Utc::now().to_rfc3339());
        self.persist();
    }

    pub fn patch_sent(&mut self) {
        self.state.patches_emitted += 1;
        self.state.last_event_at = Some(Utc::now().to_rfc3339());
        self.persist();
    }

    pub fn set_error(&mut self, message: impl Into<String>) {
        self.state.last_error = Some(message.into());
        self.persist();
    }

    pub fn complete(&mut self) {
        self.state.completed = true;
        self.state.completed_at = Some(Utc::now().to_rfc3339());
        self.persist();
    }

    fn persist(&mut self) {
        if let Some(parent) = self.path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        if let Ok(payload) = serde_json::to_string_pretty(&self.state) {
            let _ = fs::write(&self.path, payload);
        }
    }
}
