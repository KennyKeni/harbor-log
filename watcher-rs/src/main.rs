mod adapters;
mod config;
mod patching;
mod raw;
mod status;
mod tail;
mod transport;

use config::{Config, Mode};
use patching::PatchTracker;
use status::StatusWriter;
use transport::EventSender;

fn main() {
    let config = match Config::from_env() {
        Ok(config) => config,
        Err(err) => {
            eprintln!("[harbor-stream-helper] {err}");
            return;
        }
    };

    let sender = match EventSender::new(&config) {
        Ok(sender) => sender,
        Err(err) => {
            eprintln!("[harbor-stream-helper] failed to initialize HTTP client: {err}");
            return;
        }
    };
    let mut status = StatusWriter::new(config.status_path.clone(), &config.mode);
    let mut patches = PatchTracker::new(config.patch_root.clone());

    let result = match config.mode {
        Mode::Claude => adapters::claude::run(&config, &sender, &mut status, &mut patches),
        Mode::Codex => adapters::codex::run(&config, &sender, &mut status, &mut patches),
        Mode::Terminus2 => adapters::terminus2::run(&config, &sender, &mut status, &mut patches),
        Mode::Raw => raw::run(&config, &sender, &mut status),
    };

    if let Err(err) = result {
        status.set_error(err.clone());
        eprintln!("[harbor-stream-helper] {err}");
    } else {
        status.complete();
    }
}
