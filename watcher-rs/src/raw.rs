use crate::config::Config;
use crate::status::StatusWriter;
use crate::tail::TailState;
use crate::transport::EventSender;
use serde_json::json;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::thread;
use std::time::Duration;
use walkdir::WalkDir;

fn should_track(log_root: &Path, path: &Path) -> bool {
    if !path.is_file() {
        return false;
    }
    let Ok(relative) = path.strip_prefix(log_root) else {
        return false;
    };

    let name = relative.file_name().and_then(|value| value.to_str()).unwrap_or("");
    if name == "install.sh" || name == "recording.cast" {
        return false;
    }
    if name.starts_with("trajectory") && name.ends_with(".json") {
        return false;
    }

    let relative_string = relative.to_string_lossy();
    if relative_string.starts_with(".harbor-stream/")
        || relative_string.starts_with("setup/")
        || relative_string.starts_with("command-")
    {
        return false;
    }

    matches!(
        path.extension().and_then(|value| value.to_str()),
        Some("txt" | "log" | "jsonl" | "pane")
    )
}

#[cfg(test)]
mod tests {
    use super::should_track;
    use std::path::Path;

    #[test]
    fn ignores_trajectory_files() {
        assert!(!should_track(
            Path::new("/logs/agent"),
            Path::new("/logs/agent/trajectory.json"),
        ));
    }

    #[test]
    fn tracks_plain_text_logs() {
        let root = std::env::temp_dir().join("harbor-stream-helper-raw-test");
        let _ = std::fs::create_dir_all(&root);
        let path = root.join("goose.txt");
        std::fs::write(&path, "hello\n").expect("write test file");
        assert!(should_track(&root, &path));
    }
}

pub fn run(config: &Config, sender: &EventSender, status: &mut StatusWriter) -> Result<(), String> {
    let mut tails: HashMap<PathBuf, TailState> = HashMap::new();

    loop {
        for entry in WalkDir::new(&config.log_root).into_iter().filter_map(Result::ok) {
            let path = entry.path().to_path_buf();
            if should_track(&config.log_root, &path) {
                tails.entry(path).or_default();
            }
        }

        let paths: Vec<PathBuf> = tails.keys().cloned().collect();
        for path in paths {
            if let Some(state) = tails.get_mut(&path) {
                for line in state.read_new_lines(&path)? {
                    let relative = path
                        .strip_prefix(&config.log_root)
                        .unwrap_or(&path)
                        .to_string_lossy()
                        .to_string();
                    sender.send(
                        "agent.raw_line",
                        json!({
                            "path": relative,
                            "line": line,
                        }),
                    )?;
                    status.event_sent();
                }
            }
        }

        thread::sleep(Duration::from_millis(500));
    }
}
