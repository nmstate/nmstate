use std::{
    fmt::Write as _,
    ops::Deref,
    sync::{Mutex, MutexGuard},
};

use env_logger::filter::{Builder, Filter};

use log::{Log, Metadata, Record, SetLoggerError};

const FILTER_ENV: &str = "NMSTATE_LOG";

#[derive(Debug)]
struct Logger {
    inner: Filter,
    buffer: Mutex<String>,
}

impl Logger {
    fn lock(&self) -> MutexGuard<String> {
        self.buffer.lock().expect("inner lock poisoned")
    }
}

impl Log for Logger {
    fn enabled(&self, metadata: &Metadata) -> bool {
        self.inner.enabled(metadata)
    }

    fn log(&self, record: &Record) {
        if self.enabled(record.metadata()) {
            let mut buffer = self.lock();
            writeln!(buffer, "[{}] {:<5}", record.level(), record.args())
                .expect("std::fmt::Write should never fail for String");
        }
    }

    fn flush(&self) {}
}

/// A reference to the buffered data.
/// Note that this locks the logger, causing logging to block.
///
/// This type implements `Deref` for `str`, allowing access to the contents.
#[derive(Debug)]
pub struct BufferLockGuard<'a>(MutexGuard<'a, String>);

impl<'a> Deref for BufferLockGuard<'a> {
    type Target = str;

    fn deref(&self) -> &Self::Target {
        self.0.as_ref()
    }
}

/// A blocking memory logger. Logging and read operations may block.
///
/// You should have only a single instance of this in your program.
#[derive(Debug)]
pub struct MemoryLogger(Logger);

impl MemoryLogger {
    /// Initializes the global logger with a new MemoryLogger instance.
    /// This function should only be called once.
    ///
    /// ```
    /// # use memory_logger::blocking::MemoryLogger;
    /// # use regex::Regex;
    /// # fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// let logger = MemoryLogger::setup(log::Level::Info)?;
    ///
    /// log::info!("This is a info.");
    /// log::warn!("This is a warning.");
    ///
    /// let contents = logger.read();
    ///
    /// assert!(contents.contains("This is a info."));
    /// assert!(contents.contains("This is a warning."));
    /// # Ok(())
    /// # }
    /// ```
    ///
    /// Returns the installed MemoryLogger instance.
    pub fn setup() -> Result<&'static Self, SetLoggerError> {
        let mut builder = Builder::from_env(FILTER_ENV);
        let logger = Box::leak(Box::new(Self(Logger {
            inner: builder.build(),
            buffer: Mutex::new(String::new()),
        })));

        log::set_max_level(logger.0.inner.filter());
        log::set_logger(&logger.0)?;

        Ok(logger)
    }

    /// Gets a reference to the buffered data.
    /// Note that this locks the logger, causing logging to block.
    pub fn read(&self) -> BufferLockGuard {
        BufferLockGuard(self.0.lock())
    }
}
