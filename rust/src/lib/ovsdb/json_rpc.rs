// SPDX-License-Identifier: Apache-2.0

use serde::{Deserialize, Serialize};
use serde_json::Value;
use tokio::{io::AsyncWriteExt, net::UnixStream};

use crate::{ErrorKind, NmstateError};

// This buffer size is hard code in OpenvSwitch code `struct jsonrpc` of
// `lib/jsonrpc.c`. Changing it will impact `OvsDbJsonRpc::recv()`.
// Do not change unless OpenvSwitch changed so.
const BUFFER_SIZE: usize = 4096;
const MAX_RECV_RETRY_COUNT: usize = 50;

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
    pub(crate) async fn connect(
        socket_path: &str,
    ) -> Result<Self, NmstateError> {
        Ok(Self {
            socket: UnixStream::connect(socket_path).await.map_err(|e| {
                NmstateError::new(ErrorKind::Bug, format!("socket error {e}"))
            })?,
        })
    }

    pub(crate) async fn send(
        &mut self,
        data: &Value,
    ) -> Result<(), NmstateError> {
        let buffer = serde_json::to_string(&data)?;
        log::debug!("OVSDB: sending command {buffer}");
        self.socket
            .write_all(buffer.as_bytes())
            .await
            .map_err(|e| {
                NmstateError::new(
                    ErrorKind::PluginFailure,
                    format!("Failed to send message to OVSDB: {e}"),
                )
            })?;
        self.socket.flush().await.map_err(|e| {
            NmstateError::new(
                ErrorKind::PluginFailure,
                format!(
                    "Failed to flush buffer when sending message to OVSDB: {e}"
                ),
            )
        })?;
        Ok(())
    }

    // * JSON-RPC has no indicator for `end-of-message`.
    // * UnixStream has no indicator for `end-of-message`.
    // * The OpenvSwitch code `lib/jsonrpc.c` function `jsonrpc_recv` is
    //   depending on JSON parser to determine whether message ended, and keep
    //   retry for `MAX_RECV_RETRY_COUNT` count.
    pub(crate) async fn recv(
        &mut self,
        transaction_id: u64,
    ) -> Result<Value, NmstateError> {
        let mut response: Vec<u8> = Vec::with_capacity(BUFFER_SIZE);

        let mut reply: Result<OvsDbRpcReply, NmstateError> =
            Err(NmstateError::new(
                ErrorKind::PluginFailure,
                "Empty reply from OVSDB".to_string(),
            ));

        for _ in 0..MAX_RECV_RETRY_COUNT {
            self.socket.readable().await.map_err(|e| {
                NmstateError::new(
                    ErrorKind::PluginFailure,
                    format!("OVSDB connection is not readable: {e}"),
                )
            })?;
            let mut buffer = [0; BUFFER_SIZE];
            let read_size = match self.socket.try_read(&mut buffer) {
                Ok(s) => s,
                Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    continue;
                }
                Err(e) => {
                    return Err(NmstateError::new(
                        ErrorKind::PluginFailure,
                        format!(
                            "Failed to read data from OVSDB connection: {e}"
                        ),
                    ))
                }
            };
            log::debug!(
                "OVSDB: recv size {read_size}, data {:?}",
                &buffer[..read_size]
            );
            if read_size > 0 {
                response.extend_from_slice(&buffer[..read_size]);
            }

            // A better way here to parse Vec as UTF8 is using `str::from_utf8`
            // without consuming the Vec. But that function only stable
            // on Rust 1.87. Unless use `unsafe { mem::transmute() }`
            // converting &[u8] to &str, we have to clone the data here.
            match String::from_utf8(response.clone()) {
                Ok(reply_str) => {
                    log::debug!("OVSDB: recv string {:?}", &reply_str);
                    // Check whether received data is a valid JSON data which
                    // is indicator of end-of-message.
                    match serde_json::from_str::<OvsDbRpcReply>(&reply_str) {
                        Ok(r) => {
                            reply = Ok(r);
                            break;
                        }
                        Err(e) => {
                            reply = Err(NmstateError::new(
                                ErrorKind::PluginFailure,
                                format!(
                                    "OVS db reply is not valid OvsDbRpcReply: \
                                     {e}"
                                ),
                            ));
                        }
                    }
                }
                Err(e) => {
                    reply = Err(NmstateError::new(
                        ErrorKind::PluginFailure,
                        format!("OVS db reply is not valid UTF8 string: {e}"),
                    ));
                }
            }
        }

        let reply = reply?;

        if reply.id != transaction_id {
            let e = NmstateError::new(
                ErrorKind::PluginFailure,
                format!(
                    "Transaction ID mismatch for OVS DB JSON RPC: {reply:?}"
                ),
            );
            log::error!("{e}");
            Err(e)
        } else if let Some(rpc_error) = reply.error {
            let e = NmstateError::new(
                ErrorKind::PluginFailure,
                format!("OVS DB JSON RPC error: {rpc_error:?}"),
            );
            log::error!("{e}");
            Err(e)
        } else {
            Ok(reply.result)
        }
    }
}
