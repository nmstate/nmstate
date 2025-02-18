// SPDX-License-Identifier: Apache-2.0

use std::io::{Read, Write};
use std::os::unix::net::UnixStream;

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::{ErrorKind, NmstateError};

const BUFFER_SIZE: usize = 4096;

#[derive(Debug)]
pub(crate) struct OvsDbJsonRpc {
    socket: UnixStream,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default, PartialEq, Eq)]
struct OvsDbRpcRequest {
    method: String,
    params: Value,
    id: u64,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default, PartialEq, Eq)]
struct OvsDbRpcError {
    error: String,
    details: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct OvsDbRpcReply {
    // The result might also contain a error.
    result: Value,
    error: Option<OvsDbRpcError>,
    id: u64,
}

impl OvsDbJsonRpc {
    pub(crate) fn connect(socket_path: &str) -> Result<Self, NmstateError> {
        Ok(Self {
            socket: UnixStream::connect(socket_path).map_err(|e| {
                NmstateError::new(ErrorKind::Bug, format!("socket error {e}"))
            })?,
        })
    }

    pub(crate) fn send(&mut self, data: &Value) -> Result<(), NmstateError> {
        let buffer = serde_json::to_string(&data)?;
        log::debug!("OVSDB: sending command {}", buffer);
        self.socket
            .write_all(buffer.as_bytes())
            .map_err(parse_socket_io_error)?;
        Ok(())
    }

    pub(crate) fn recv(
        &mut self,
        transaction_id: u64,
    ) -> Result<Value, NmstateError> {
        let mut response: Vec<u8> = Vec::new();
        loop {
            let mut buffer = [0u8; BUFFER_SIZE];
            let read = self
                .socket
                .read(&mut buffer)
                .map_err(parse_socket_io_error)?;
            log::debug!("OVSDB: recv data {:?}", &buffer[..read]);
            response.extend_from_slice(&buffer[..read]);
            if read < BUFFER_SIZE {
                break;
            }
        }
        let reply_string =
            String::from_utf8(response).map_err(parse_str_parse_error)?;
        log::debug!("OVSDB: recv string {:?}", &reply_string);
        let reply: OvsDbRpcReply = serde_json::from_str(&reply_string)?;
        if reply.id != transaction_id {
            let e = NmstateError::new(
                ErrorKind::PluginFailure,
                format!(
                    "Transaction ID mismatch for OVS DB JSON RPC: {reply:?}"
                ),
            );
            log::error!("{}", e);
            Err(e)
        } else if let Some(rpc_error) = reply.error {
            let e = NmstateError::new(
                ErrorKind::PluginFailure,
                format!("OVS DB JSON RPC error: {rpc_error:?}"),
            );
            log::error!("{}", e);
            Err(e)
        } else {
            Ok(reply.result)
        }
    }
}

fn parse_str_parse_error(e: std::string::FromUtf8Error) -> NmstateError {
    NmstateError::new(
        ErrorKind::PluginFailure,
        format!("Reply from OVSDB is not valid UTF-8 string: {e}"),
    )
}

fn parse_socket_io_error(e: std::io::Error) -> NmstateError {
    NmstateError::new(
        ErrorKind::PluginFailure,
        format!("OVSDB Socket error: {e}"),
    )
}
