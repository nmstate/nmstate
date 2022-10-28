// SPDX-License-Identifier: Apache-2.0

use crate::error::CliError;

pub(crate) fn print_result_and_exit(result: Result<String, CliError>) {
    match result {
        Ok(s) => {
            println!("{s}");
            std::process::exit(0);
        }
        Err(e) => {
            eprintln!("{}", e.error_msg);
            std::process::exit(e.code);
        }
    }
}
