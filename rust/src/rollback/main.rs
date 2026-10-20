// SPDX-License-Identifier: Apache-2.0

#[tokio::main(flavor = "current_thread")]
async fn main() -> std::process::ExitCode {
    env_logger::init();
    match nmstate::run_rollback_service().await {
        Ok(()) => std::process::ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("nmstate rollback service: {error}");
            std::process::ExitCode::FAILURE
        }
    }
}
