use std::env;
use std::path::PathBuf;

#[derive(Clone, Debug)]
pub enum Mode {
    Claude,
    Codex,
    Terminus2,
    Raw,
}

#[derive(Clone, Debug)]
pub struct Meta {
    pub job_name: String,
    pub trial_id: String,
    pub task_name: String,
    pub agent_name: String,
    pub environment_type: String,
}

#[derive(Clone, Debug)]
pub struct Config {
    pub mode: Mode,
    pub stream_url: String,
    pub stream_token: Option<String>,
    pub log_root: PathBuf,
    pub patch_root: Option<PathBuf>,
    pub status_path: PathBuf,
    pub meta: Meta,
}

impl Config {
    pub fn from_env() -> Result<Self, String> {
        let mode = match env::var("HARBOR_STREAM_MODE")
            .map_err(|_| "HARBOR_STREAM_MODE is required".to_string())?
            .to_lowercase()
            .as_str()
        {
            "claude" => Mode::Claude,
            "codex" => Mode::Codex,
            "terminus2" => Mode::Terminus2,
            "raw" => Mode::Raw,
            other => return Err(format!("unsupported helper mode: {other}")),
        };

        let stream_url = env::var("HARBOR_STREAM_STREAM_URL")
            .map_err(|_| "HARBOR_STREAM_STREAM_URL is required".to_string())?;
        let stream_token = env::var("HARBOR_STREAM_STREAM_TOKEN").ok();
        let log_root = PathBuf::from(
            env::var("HARBOR_STREAM_LOG_ROOT").unwrap_or_else(|_| "/logs/agent".into()),
        );
        let patch_root = env::var("HARBOR_STREAM_PATCH_ROOT")
            .ok()
            .filter(|value| !value.is_empty())
            .map(PathBuf::from);
        let status_path = PathBuf::from(
            env::var("HARBOR_STREAM_STATUS_PATH")
                .unwrap_or_else(|_| "/logs/agent/.harbor-stream/status.json".into()),
        );

        let meta = Meta {
            job_name: env::var("HARBOR_STREAM_JOB_NAME")
                .unwrap_or_else(|_| "unknown-job".into()),
            trial_id: env::var("HARBOR_STREAM_TRIAL_ID")
                .unwrap_or_else(|_| "unknown-trial".into()),
            task_name: env::var("HARBOR_STREAM_TASK_NAME")
                .unwrap_or_else(|_| "unknown-task".into()),
            agent_name: env::var("HARBOR_STREAM_AGENT_NAME")
                .unwrap_or_else(|_| "unknown-agent".into()),
            environment_type: env::var("HARBOR_STREAM_ENVIRONMENT_TYPE")
                .unwrap_or_else(|_| "".into()),
        };

        Ok(Self {
            mode,
            stream_url,
            stream_token,
            log_root,
            patch_root,
            status_path,
            meta,
        })
    }

    pub fn claude_log_path(&self) -> PathBuf {
        self.log_root.join("claude-code.txt")
    }

    pub fn codex_log_path(&self) -> PathBuf {
        self.log_root.join("codex.txt")
    }
}
