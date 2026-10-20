// SPDX-License-Identifier: Apache-2.0

use std::{
    fs::OpenOptions,
    os::unix::fs::{FileTypeExt, MetadataExt, OpenOptionsExt, PermissionsExt},
    path::{Path, PathBuf},
    time::Duration,
};

use nix::fcntl::{Flock, FlockArg};
use serde::{Deserialize, Serialize, de::DeserializeOwned};
use tokio::{
    io::{AsyncReadExt, AsyncWriteExt},
    net::{UnixListener, UnixStream},
};

use super::{
    Context, current_identity, failure,
    journal::{DIRECTORY, Identity, Namespace, Phase, check_directory},
    permission,
};
use crate::{ErrorKind, InterfaceType, NetworkState, NmstateError};

const SOCKET: &str = "/run/nmstate/rollback/control.sock";
const MAX_MESSAGE: usize = 16 * 1024 * 1024;
const READ_TIMEOUT: Duration = Duration::from_secs(10);
// Context::finish gives up after 45 seconds.
const FINISH_TIMEOUT: Duration = Duration::from_secs(60);

#[derive(Deserialize, Serialize)]
#[serde(deny_unknown_fields)]
struct ApplyRequest {
    state: NetworkState,
    interface_order: Vec<(String, InterfaceType)>,
    no_verify: bool,
    no_commit: bool,
    timeout: Option<u32>,
    memory_only: bool,
    override_iface: bool,
}

impl From<&NetworkState> for ApplyRequest {
    fn from(state: &NetworkState) -> Self {
        Self {
            state: state.clone(),
            interface_order: state.interfaces.insert_order.clone(),
            no_verify: state.no_verify,
            no_commit: state.no_commit,
            timeout: state.timeout,
            memory_only: state.memory_only,
            override_iface: state.override_iface,
        }
    }
}

impl ApplyRequest {
    fn into_state(self) -> NetworkState {
        let mut state = self.state;
        state.interfaces.insert_order = self.interface_order;
        state.no_verify = self.no_verify;
        state.no_commit = self.no_commit;
        state.timeout = self.timeout;
        state.memory_only = self.memory_only;
        state.override_iface = self.override_iface;
        state
    }
}

#[derive(Deserialize, Serialize)]
enum Request {
    Apply {
        expected: Identity,
        dispatch_dir: PathBuf,
        request: Box<ApplyRequest>,
    },
    Finish {
        expected: Identity,
        checkpoint: String,
        commit: bool,
    },
}

#[derive(Deserialize, Serialize)]
enum Response {
    Applied(String),
    Finished(bool),
}

type Reply = Result<Response, NmstateError>;

pub(super) async fn apply(
    state: &NetworkState,
) -> Result<String, NmstateError> {
    let expected = current_identity().await?;
    let mut stream = connect().await?;
    write_message(
        &mut stream,
        &Request::Apply {
            expected,
            dispatch_dir: dispatch_directory()?,
            request: Box::new(state.into()),
        },
    )
    .await?;
    match read_message::<Reply>(&mut stream).await?? {
        Response::Applied(checkpoint) => Ok(checkpoint),
        _ => Err(failure("Invalid response from recovery service")),
    }
}

pub(super) async fn finish(
    checkpoint: &str,
    commit: bool,
) -> Result<bool, NmstateError> {
    match std::fs::symlink_metadata(
        Path::new(DIRECTORY).join("transaction.json"),
    ) {
        Ok(metadata)
            if metadata.is_file()
                && metadata.uid() == 0
                && metadata.nlink() == 1
                && metadata.permissions().mode() & 0o077 == 0 => {}
        Ok(_) => {
            return Err(permission(
                "Recovery journal is not a private root-owned file",
            ));
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(false),
        Err(e) => {
            return Err(failure(format!(
                "Cannot inspect recovery journal: {e}"
            )));
        }
    }
    let expected = current_identity().await?;
    let mut stream = connect().await?;
    write_message(
        &mut stream,
        &Request::Finish {
            expected,
            checkpoint: checkpoint.into(),
            commit,
        },
    )
    .await?;
    let reply = tokio::time::timeout(
        FINISH_TIMEOUT,
        read_message::<Reply>(&mut stream),
    )
    .await
    .map_err(|_| failure("Timed out waiting for recovery service"))?;
    match reply?? {
        Response::Finished(owned) => Ok(owned),
        _ => Err(failure("Invalid response from recovery service")),
    }
}

async fn connect() -> Result<UnixStream, NmstateError> {
    let started = tokio::time::Instant::now();
    let mut activation_requested = false;
    loop {
        if Path::new(DIRECTORY).exists() {
            check_directory(Path::new("/run/nmstate"))?;
            check_directory(Path::new(DIRECTORY))?;
        }
        match std::fs::symlink_metadata(SOCKET) {
            Ok(metadata) => {
                if !metadata.file_type().is_socket()
                    || metadata.uid() != 0
                    || metadata.permissions().mode() & 0o077 != 0
                {
                    return Err(permission(
                        "Recovery socket must be a private root-owned Unix \
                         socket",
                    ));
                }
            }
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
            Err(e) => {
                return Err(failure(format!(
                    "Cannot inspect recovery socket: {e}"
                )));
            }
        }
        match UnixStream::connect(SOCKET).await {
            Ok(stream) => {
                check_peer(&stream)?;
                return Ok(stream);
            }
            Err(e)
                if matches!(
                    e.kind(),
                    std::io::ErrorKind::NotFound
                        | std::io::ErrorKind::ConnectionRefused
                ) => {}
            Err(e) => {
                return Err(failure(format!(
                    "Cannot connect to recovery service: {e}"
                )));
            }
        }
        if started.elapsed() >= Duration::from_secs(30) {
            return Err(NmstateError::new(
                ErrorKind::DependencyError,
                "Recovery service did not become ready".into(),
            ));
        }
        if !activation_requested {
            activate_service().await?;
            activation_requested = true;
        }
        tokio::time::sleep(Duration::from_millis(100)).await;
    }
}

async fn activate_service() -> Result<(), NmstateError> {
    tokio::time::timeout(Duration::from_secs(10), request_activation())
        .await
        .map_err(|_| {
            NmstateError::new(
                ErrorKind::DependencyError,
                "Timed out starting recovery service".into(),
            )
        })?
}

async fn request_activation() -> Result<(), NmstateError> {
    let connection = zbus::Connection::system().await.map_err(|e| {
        NmstateError::new(
            ErrorKind::DependencyError,
            format!("Cannot connect to systemd for recovery service: {e}"),
        )
    })?;
    let proxy = zbus::Proxy::new(
        &connection,
        "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1",
        "org.freedesktop.systemd1.Manager",
    )
    .await
    .map_err(|e| {
        NmstateError::new(
            ErrorKind::DependencyError,
            format!("Cannot activate recovery service: {e}"),
        )
    })?;
    let _: zvariant::OwnedObjectPath = proxy
        .call("StartUnit", &("nmstate-rollback.service", "replace"))
        .await
        .map_err(|e| {
            NmstateError::new(
                ErrorKind::DependencyError,
                format!("Cannot start nmstate-rollback.service: {e}"),
            )
        })?;
    Ok(())
}

fn check_peer(stream: &UnixStream) -> Result<(), NmstateError> {
    let credentials = stream.peer_cred().map_err(|e| {
        permission(format!("Cannot authenticate recovery peer: {e}"))
    })?;
    let pid = credentials
        .pid()
        .ok_or_else(|| permission("Recovery peer has no visible process"))?;
    if credentials.uid() != 0 || pid <= 0 {
        return Err(permission("Recovery operations require a root process"));
    }
    let namespace = Namespace::read("/proc/self/ns/net")?;
    if Namespace::read(format!("/proc/{pid}/ns/net"))? != namespace {
        return Err(permission(
            "Recovery peer is in a different network namespace",
        ));
    }
    let peer_user_namespace = Namespace::read(format!("/proc/{pid}/ns/user"))?;
    let own_user_namespace = Namespace::read("/proc/self/ns/user")?;
    let status = std::fs::read_to_string(format!("/proc/{pid}/status"))
        .map_err(|e| {
            permission(format!(
                "Cannot inspect recovery peer capabilities: {e}"
            ))
        })?;
    if !net_admin_in_namespace(
        &status,
        &peer_user_namespace,
        &own_user_namespace,
    )? {
        return Err(permission(
            "Recovery operations require CAP_NET_ADMIN in the host user \
             namespace",
        ));
    }
    Ok(())
}

fn check_apply_peer(stream: &UnixStream) -> Result<(), NmstateError> {
    let pid = stream
        .peer_cred()
        .map_err(|e| {
            permission(format!("Cannot authenticate apply caller: {e}"))
        })?
        .pid()
        .filter(|pid| *pid > 0)
        .ok_or_else(|| permission("Apply caller has no visible process"))?;
    for (namespace, name) in [("mnt", "mount"), ("uts", "UTS")] {
        if Namespace::read(format!("/proc/{pid}/ns/{namespace}"))?
            != Namespace::read(format!("/proc/self/ns/{namespace}"))?
        {
            return Err(permission(format!(
                "External-rule apply requires the caller and recovery service \
                 to share the same {name} namespace"
            )));
        }
    }
    if Namespace::read(format!("/proc/{pid}/root"))?
        != Namespace::read("/proc/self/root")?
    {
        return Err(permission(
            "External-rule apply requires the caller and recovery service to \
             share the same filesystem root",
        ));
    }
    let peer_status = std::fs::read_to_string(format!("/proc/{pid}/status"))
        .map_err(|e| {
            permission(format!("Cannot inspect apply caller capabilities: {e}"))
        })?;
    let own_status =
        std::fs::read_to_string("/proc/self/status").map_err(|e| {
            permission(format!(
                "Cannot inspect recovery service capabilities: {e}"
            ))
        })?;
    let required = effective_capabilities(&own_status)?;
    if effective_capabilities(&peer_status)? & required != required {
        return Err(permission(
            "External-rule apply requires all effective capabilities held by \
             the recovery service",
        ));
    }
    Ok(())
}

fn dispatch_directory() -> Result<PathBuf, NmstateError> {
    std::path::absolute(crate::nm::dispatch_dir()).map_err(|e| {
        failure(format!("Cannot resolve dispatcher directory: {e}"))
    })
}

pub(super) fn has_host_net_admin() -> Result<bool, NmstateError> {
    let status = std::fs::read_to_string("/proc/self/status").map_err(|e| {
        failure(format!("Cannot inspect process capabilities: {e}"))
    })?;
    net_admin_in_namespace(
        &status,
        &Namespace::read("/proc/self/ns/user")?,
        &Namespace::read("/proc/1/ns/user")?,
    )
}

fn net_admin_in_namespace(
    status: &str,
    peer_namespace: &Namespace,
    own_namespace: &Namespace,
) -> Result<bool, NmstateError> {
    if peer_namespace != own_namespace {
        return Ok(false);
    }
    has_net_admin(status)
}

fn has_net_admin(status: &str) -> Result<bool, NmstateError> {
    Ok(effective_capabilities(status)? & (1 << 12) != 0)
}

fn effective_capabilities(status: &str) -> Result<u64, NmstateError> {
    status
        .lines()
        .find_map(|line| line.strip_prefix("CapEff:\t"))
        .and_then(|s| u64::from_str_radix(s.trim(), 16).ok())
        .ok_or_else(|| {
            permission("Cannot read recovery peer effective capabilities")
        })
}

async fn read_message<T: DeserializeOwned>(
    stream: &mut UnixStream,
) -> Result<T, NmstateError> {
    let length = stream
        .read_u32()
        .await
        .map_err(|e| failure(format!("Recovery connection ended: {e}")))?
        as usize;
    if length == 0 || length > MAX_MESSAGE {
        return Err(failure("Recovery message exceeds its size limit"));
    }
    let mut bytes = vec![0; length];
    stream
        .read_exact(&mut bytes)
        .await
        .map_err(|e| failure(format!("Cannot read recovery request: {e}")))?;
    serde_json::from_slice(&bytes)
        .map_err(|e| failure(format!("Invalid recovery message: {e}")))
}

async fn write_message<T: Serialize>(
    stream: &mut UnixStream,
    value: &T,
) -> Result<(), NmstateError> {
    let bytes = serde_json::to_vec(value)
        .map_err(|e| failure(format!("Cannot encode recovery message: {e}")))?;
    if bytes.len() > MAX_MESSAGE {
        return Err(failure("Recovery message exceeds its size limit"));
    }
    stream
        .write_u32(bytes.len() as u32)
        .await
        .map_err(|e| failure(format!("Cannot send recovery message: {e}")))?;
    stream
        .write_all(&bytes)
        .await
        .map_err(|e| failure(format!("Cannot send recovery message: {e}")))
}

pub(super) async fn run_service() -> Result<(), NmstateError> {
    if unsafe { nix::libc::geteuid() } != 0 {
        return Err(permission("Recovery service must run as root"));
    }
    nix::sys::stat::umask(nix::sys::stat::Mode::from_bits_truncate(0o077));
    if Namespace::read("/proc/self/ns/net")?
        != Namespace::read("/proc/1/ns/net")?
    {
        return Err(permission(
            "Recovery service must use the host network namespace",
        ));
    }
    if Namespace::read("/proc/self/ns/user")?
        != Namespace::read("/proc/1/ns/user")?
    {
        return Err(permission(
            "Recovery service must use the host user namespace",
        ));
    }
    for path in ["/run/nmstate", DIRECTORY] {
        match std::fs::create_dir(path) {
            Ok(()) => (),
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => (),
            Err(e) => {
                return Err(failure(format!(
                    "Cannot create recovery directory: {e}"
                )));
            }
        }
        check_directory(Path::new(path))?;
        std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o711))
            .map_err(|e| {
                failure(format!("Cannot protect recovery directory: {e}"))
            })?;
    }
    let lock = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .mode(0o600)
        .custom_flags(nix::libc::O_NOFOLLOW | nix::libc::O_CLOEXEC)
        .open(Path::new(DIRECTORY).join("service.lock"))
        .map_err(|e| failure(format!("Cannot open recovery lock: {e}")))?;
    let _lock = Flock::lock(lock, FlockArg::LockExclusiveNonblock).map_err(
        |(_, e)| failure(format!("Another recovery service is running: {e}")),
    )?;
    let context = Context::load()?;
    if let Err(error) = context.recover().await {
        log::error!("Recovery remains pending: {error}");
    }
    match std::fs::symlink_metadata(SOCKET) {
        Ok(metadata)
            if metadata.file_type().is_socket() && metadata.uid() == 0 =>
        {
            std::fs::remove_file(SOCKET).map_err(|e| {
                failure(format!("Cannot replace old recovery socket: {e}"))
            })?;
        }
        Ok(_) => {
            return Err(permission(
                "Recovery socket path is not a root-owned socket",
            ));
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => (),
        Err(e) => {
            return Err(failure(format!(
                "Cannot inspect recovery socket: {e}"
            )));
        }
    }
    let listener = UnixListener::bind(SOCKET)
        .map_err(|e| failure(format!("Cannot bind recovery socket: {e}")))?;
    std::fs::set_permissions(SOCKET, std::fs::Permissions::from_mode(0o600))
        .map_err(|e| failure(format!("Cannot protect recovery socket: {e}")))?;
    loop {
        tokio::select! {
            result = context.wait_for_deadline() => {
                result?;
                if let Err(error) = context.finish("", false).await {
                    log::error!("Automatic rollback failed: {error}");
                    tokio::time::sleep(Duration::from_secs(1)).await;
                }
            }
            accepted = listener.accept() => {
                let (mut stream, _) = accepted.map_err(|e| failure(format!("Cannot accept recovery request: {e}")))?;
                let result = handle_request(&mut stream, &context).await;
                let _ = tokio::time::timeout(Duration::from_secs(5), write_message(&mut stream, &result)).await;
            }
            _ = tokio::time::sleep(Duration::from_secs(2)) => {
                let retry = context.inner.lock().await.as_ref().is_some_and(|record| {
                    matches!(record.phase, Phase::Preparing | Phase::Applying | Phase::Commit | Phase::Rollback)
                });
                if retry && let Err(error) = context.recover().await {
                    log::error!("Recovery remains pending: {error}");
                }
            }
        }
    }
}

async fn handle_request(stream: &mut UnixStream, context: &Context) -> Reply {
    check_peer(stream)?;
    let request = tokio::select! {
        result = tokio::time::timeout(READ_TIMEOUT, read_message::<Request>(stream)) => {
            result.map_err(|_| failure("Recovery request timed out"))??
        }
        result = context.wait_for_deadline() => {
            result?;
            context.finish("", false).await?;
            return Err(failure("Checkpoint expired while reading recovery request"));
        }
    };
    match request {
        Request::Finish {
            expected,
            checkpoint,
            commit,
        } => {
            if expected != current_identity().await? {
                return Err(permission(
                    "Caller and recovery service refer to different \
                     NetworkManager instances",
                ));
            }
            context
                .finish(&checkpoint, commit)
                .await
                .map(Response::Finished)
        }
        Request::Apply {
            expected,
            dispatch_dir,
            request,
        } => {
            check_apply_peer(stream)?;
            if dispatch_dir != dispatch_directory()? {
                return Err(permission(
                    "External-rule apply requires the caller and recovery \
                     service to use the same dispatcher directory",
                ));
            }
            if expected != current_identity().await? {
                return Err(permission(
                    "Caller and recovery service refer to different \
                     NetworkManager instances",
                ));
            }
            if context.inner.lock().await.is_some() {
                return Err(failure(
                    "A checkpoint is pending; commit or roll it back before \
                     applying another state",
                ));
            }
            let state = request.into_state();
            let result = connected_apply(
                stream,
                context.run_apply(&state),
                context.wait_for_deadline(),
            )
            .await;
            match result {
                Ok(checkpoint) => Ok(Response::Applied(checkpoint)),
                Err(error) => {
                    if let Err(rollback) = context.finish("", false).await {
                        Err(NmstateError::new(
                            error.kind(),
                            format!(
                                "{error}; rollback remains pending: {rollback}"
                            ),
                        ))
                    } else {
                        Err(error)
                    }
                }
            }
        }
    }
}

async fn connected_apply<T>(
    stream: &mut UnixStream,
    apply: impl std::future::Future<Output = Result<T, NmstateError>>,
    deadline: impl std::future::Future<Output = Result<(), NmstateError>>,
) -> Result<T, NmstateError> {
    let mut unexpected = [0u8; 1];
    tokio::select! {
        result = apply => result,
        _ = stream.read(&mut unexpected) => Err(failure("Apply caller disconnected before completion")),
        result = deadline => {
            result.and(Err(failure("Apply exceeded its rollback deadline")))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn oversized_frame_is_rejected_before_reading_body() {
        let (mut client, mut server) = UnixStream::pair().unwrap();
        client.write_u32(MAX_MESSAGE as u32 + 1).await.unwrap();
        // The client stays open, so reading the body would block.
        assert!(read_message::<Request>(&mut server).await.is_err());
    }

    #[tokio::test]
    async fn truncated_frame_is_rejected() {
        let (mut client, mut server) = UnixStream::pair().unwrap();
        client.write_u32(10).await.unwrap();
        client.write_all(b"{}").await.unwrap();
        drop(client);
        assert!(read_message::<Request>(&mut server).await.is_err());
    }

    #[tokio::test]
    async fn flags_survive_process_boundary() {
        let (mut client, mut server) = UnixStream::pair().unwrap();
        let mut state = NetworkState::new();
        state.no_verify = true;
        state.no_commit = true;
        state.memory_only = true;
        state.override_iface = true;
        state.timeout = Some(17);
        let expected = Identity {
            boot: "test-boot".into(),
            namespace: Namespace::read("/proc/self/ns/net").unwrap(),
            user_namespace: Namespace::read("/proc/self/ns/user").unwrap(),
            nm_owner: ":1.17".into(),
            bus_id: "test-bus".into(),
        };
        write_message(
            &mut client,
            &Request::Apply {
                expected,
                dispatch_dir: dispatch_directory().unwrap(),
                request: Box::new((&state).into()),
            },
        )
        .await
        .unwrap();
        let Request::Apply {
            request,
            dispatch_dir,
            ..
        } = read_message::<Request>(&mut server).await.unwrap()
        else {
            panic!("wrong request")
        };
        let restored = request.into_state();
        assert_eq!(dispatch_dir, dispatch_directory().unwrap());
        assert!(restored.no_verify);
        assert!(restored.no_commit);
        assert!(restored.memory_only);
        assert!(restored.override_iface);
        assert_eq!(restored.timeout, Some(17));
    }

    #[tokio::test]
    async fn matching_apply_execution_context_is_accepted() {
        let (_client, server) = UnixStream::pair().unwrap();
        check_apply_peer(&server).unwrap();
    }

    #[tokio::test]
    async fn deep_controller_order_survives_process_boundary() {
        use crate::{MergedInterfaces, unit_tests::testlib::new_br_iface};

        let mut desired = NetworkState::new();
        for level in (0..=6).rev() {
            let mut iface = new_br_iface(&format!("br{level}"));
            if level < 6 {
                iface.base_iface_mut().controller =
                    Some(format!("br{}", level + 1));
                iface.base_iface_mut().controller_type =
                    Some(InterfaceType::LinuxBridge);
            }
            desired.interfaces.push(iface);
        }
        let merge = |state: NetworkState| {
            MergedInterfaces::new(
                state.interfaces,
                Default::default(),
                Default::default(),
                false,
            )
        };
        assert!(merge(desired.clone()).is_ok());
        let sorted: NetworkState =
            serde_json::from_slice(&serde_json::to_vec(&desired).unwrap())
                .unwrap();
        assert_eq!(
            merge(sorted).unwrap_err().kind(),
            ErrorKind::InvalidArgument
        );

        let (mut client, mut server) = UnixStream::pair().unwrap();
        write_message(&mut client, &ApplyRequest::from(&desired))
            .await
            .unwrap();
        let restored = read_message::<ApplyRequest>(&mut server)
            .await
            .unwrap()
            .into_state();
        assert_eq!(
            restored.interfaces.insert_order,
            desired.interfaces.insert_order
        );
        let merged = merge(restored).unwrap();
        assert_eq!(
            merged.kernel_ifaces["br0"]
                .for_apply
                .as_ref()
                .unwrap()
                .base_iface()
                .up_priority,
            6
        );
    }

    #[tokio::test]
    async fn caller_disconnect_drops_apply_before_rollback_can_start() {
        use std::sync::{
            Arc,
            atomic::{AtomicBool, Ordering},
        };

        struct ApplyGuard(Arc<AtomicBool>);
        impl Drop for ApplyGuard {
            fn drop(&mut self) {
                self.0.store(true, Ordering::SeqCst);
            }
        }
        let (client, mut server) = UnixStream::pair().unwrap();
        let cancelled = Arc::new(AtomicBool::new(false));
        let (started, ready) = tokio::sync::oneshot::channel();
        let guard = ApplyGuard(cancelled.clone());
        let apply = async move {
            let _guard = guard;
            started.send(()).unwrap();
            std::future::pending::<Result<(), NmstateError>>().await
        };
        let close = async move {
            ready.await.unwrap();
            drop(client);
        };
        let (result, ()) = tokio::join!(
            connected_apply(&mut server, apply, std::future::pending()),
            close,
        );
        assert!(result.is_err());
        assert!(cancelled.load(Ordering::SeqCst));
    }

    #[test]
    fn dropped_capability_is_not_recovered_from_root_uid() {
        assert!(
            !has_net_admin("Uid:\t0\t0\t0\t0\nCapEff:\t0000000000000000\n")
                .unwrap()
        );
        assert!(has_net_admin("CapEff:\t0000000000001000\n").unwrap());
        assert!(has_net_admin("CapEff:\tnot-hex\n").is_err());
    }

    #[test]
    fn child_namespace_capability_cannot_authorize_host_mutation() {
        let host: Namespace = serde_json::from_value(
            serde_json::json!({ "device": 1, "inode": 2 }),
        )
        .unwrap();
        let child: Namespace = serde_json::from_value(
            serde_json::json!({ "device": 1, "inode": 3 }),
        )
        .unwrap();
        let status = "Uid:\t0\t0\t0\t0\nCapEff:\t0000000000001000\n";
        assert!(!net_admin_in_namespace(status, &child, &host).unwrap());
        assert!(net_admin_in_namespace(status, &host, &host).unwrap());
    }
}
