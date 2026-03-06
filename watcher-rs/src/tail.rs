use std::fs::File;
use std::io::{Read, Seek, SeekFrom};
use std::path::Path;
use std::thread;
use std::time::{Duration, Instant};

#[derive(Default)]
pub struct TailState {
    offset: u64,
    partial: String,
}

impl TailState {
    pub fn read_new_lines(&mut self, path: &Path) -> Result<Vec<String>, String> {
        if !path.exists() {
            return Ok(Vec::new());
        }

        let metadata = path.metadata().map_err(|err| err.to_string())?;
        if metadata.len() < self.offset {
            self.offset = 0;
            self.partial.clear();
        }

        let mut file = File::open(path).map_err(|err| err.to_string())?;
        file.seek(SeekFrom::Start(self.offset))
            .map_err(|err| err.to_string())?;
        let mut chunk = String::new();
        file.read_to_string(&mut chunk)
            .map_err(|err| err.to_string())?;
        self.offset = file.stream_position().map_err(|err| err.to_string())?;

        let mut lines = Vec::new();
        for piece in chunk.split_inclusive('\n') {
            if piece.ends_with('\n') {
                self.partial.push_str(piece.trim_end_matches('\n'));
                lines.push(std::mem::take(&mut self.partial));
            } else {
                self.partial.push_str(piece);
            }
        }
        Ok(lines)
    }
}

pub fn wait_for_path(path: &Path, timeout: Duration) -> bool {
    let started = Instant::now();
    while started.elapsed() < timeout {
        if path.exists() {
            return true;
        }
        thread::sleep(Duration::from_millis(500));
    }
    false
}
