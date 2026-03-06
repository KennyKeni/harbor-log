use crate::config::Config;
use chrono::Utc;
use reqwest::blocking::Client;
use serde_json::{json, Value};
use std::sync::atomic::{AtomicU64, Ordering};
use std::thread;
use std::time::Duration;

static EVENT_COUNTER: AtomicU64 = AtomicU64::new(1);

pub struct EventSender {
    client: Client,
    config: Config,
}

impl EventSender {
    pub fn new(config: &Config) -> Result<Self, String> {
        let client = Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .map_err(|err| err.to_string())?;
        Ok(Self {
            client,
            config: config.clone(),
        })
    }

    pub fn send(&self, event_type: &str, data: Value) -> Result<(), String> {
        self.send_with_delivery("live", event_type, data)
    }

    pub fn send_with_delivery(
        &self,
        delivery: &str,
        event_type: &str,
        data: Value,
    ) -> Result<(), String> {
        let payload = json!({
            "schema_version": 1,
            "event_id": format!(
                "helper-{}-{}",
                Utc::now().timestamp_millis(),
                EVENT_COUNTER.fetch_add(1, Ordering::Relaxed)
            ),
            "timestamp": Utc::now().to_rfc3339(),
            "source": "helper",
            "delivery": delivery,
            "job_name": self.config.meta.job_name,
            "trial_id": self.config.meta.trial_id,
            "task_name": self.config.meta.task_name,
            "agent_name": self.config.meta.agent_name,
            "environment_type": self.config.meta.environment_type,
            "event_type": event_type,
            "data": data,
        });

        for attempt in 0..3 {
            let mut request = self
                .client
                .post(&self.config.stream_url)
                .json(&payload)
                .header("Content-Type", "application/json");
            if let Some(token) = &self.config.stream_token {
                request = request.bearer_auth(token);
            }

            match request.send() {
                Ok(response) if response.status().is_success() => return Ok(()),
                Ok(response) => {
                    if attempt == 2 {
                        return Err(format!("unexpected HTTP status {}", response.status()));
                    }
                }
                Err(err) => {
                    if attempt == 2 {
                        return Err(err.to_string());
                    }
                }
            }

            thread::sleep(Duration::from_millis(250 * (attempt + 1) as u64));
        }

        Err("failed to deliver event".into())
    }
}
