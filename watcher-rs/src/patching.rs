use serde_json::{json, Value};
use std::fs;
use std::path::PathBuf;
use std::process::Command;

const PATCH_MAX_SIZE: usize = 50 * 1024;
const PATCH_GIT_DIR: &str = "/tmp/.harbor-stream-patch-tracker";

pub struct PatchTracker {
    git_dir: PathBuf,
    work_tree: Option<PathBuf>,
    enabled: bool,
    step: u32,
}

impl PatchTracker {
    pub fn new(work_tree: Option<PathBuf>) -> Self {
        let mut tracker = Self {
            git_dir: PathBuf::from(PATCH_GIT_DIR),
            work_tree,
            enabled: false,
            step: 0,
        };
        tracker.enabled = tracker.init();
        tracker
    }

    pub fn enabled(&self) -> bool {
        self.enabled
    }

    pub fn snapshot(&mut self, tool_name: &str, call_id: Option<&str>) -> Option<Value> {
        if !self.enabled {
            return None;
        }

        self.git_cmd(&["add", "-Af"])?;
        let diff = self.git_cmd(&["diff", "--cached"])?;
        if diff.trim().is_empty() {
            return None;
        }

        let files_changed: Vec<String> = diff
            .lines()
            .filter(|line| line.starts_with("diff --git"))
            .filter_map(|line| line.split(" b/").nth(1).map(|part| part.to_string()))
            .collect();

        let truncated = diff.len() > PATCH_MAX_SIZE;
        let patch = if truncated {
            diff.chars().take(PATCH_MAX_SIZE).collect::<String>()
        } else {
            diff
        };

        self.step += 1;
        let message = format!("step_{}_{}", self.step, tool_name);
        self.git_cmd(&["commit", "-q", "-m", &message])?;

        Some(json!({
            "step": self.step,
            "tool_name": tool_name,
            "call_id": call_id,
            "patch": patch,
            "files_changed": files_changed,
            "truncated": truncated,
        }))
    }

    fn init(&mut self) -> bool {
        let Some(work_tree) = &self.work_tree else {
            return false;
        };
        if !work_tree.exists() {
            return false;
        }
        let _ = fs::remove_dir_all(&self.git_dir);
        let _ = fs::create_dir_all(&self.git_dir);
        if self.git_cmd(&["init", "-q"]).is_none() {
            return false;
        }
        let _ = self.git_cmd(&["config", "user.email", "watcher@harbor-stream"]);
        let _ = self.git_cmd(&["config", "user.name", "harbor-stream"]);
        let _ = fs::write(self.git_dir.join("info").join("exclude"), ".git\n");
        if self.git_cmd(&["add", "-Af"]).is_none() {
            return false;
        }
        self.git_cmd(&["commit", "-q", "-m", "initial", "--allow-empty"])
            .is_some()
    }

    fn git_cmd(&self, args: &[&str]) -> Option<String> {
        let work_tree = self.work_tree.as_ref()?;
        let output = Command::new("git")
            .env("GIT_DIR", &self.git_dir)
            .env("GIT_WORK_TREE", work_tree)
            .args(args)
            .output()
            .ok()?;
        if !output.status.success() {
            return None;
        }
        Some(String::from_utf8_lossy(&output.stdout).to_string())
    }
}
