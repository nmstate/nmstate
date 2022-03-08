## Top design
 * Top level code
    * Merging from current status
    * Verification
 * Native Plugins
    * Nispor
        * Query Kernel network status
        * TBD: Apply in-memory network config
    * NetworkManager
        * Persist network config with checkpoint support

 * TBD: Third party plugin
    * Plugin is executable file.
    * The libnmstate will start the plugin with socket patch as first argument.
    * The libnmstate will communicate with plugin through this socket path.
    * JSON format is used for request and reply.


## NetworkManager plugin
 * Use DBUS interface via crate `libnm_dbus` for communication with NM daemon.
 * Update keyfile base on desire and current config.
 * Create check point
 * Instruct NM daemon to reload config.
 * Grouping activation.
 * Skip activation of certain interface if state match.
 * Destroy or rollback checkpoint

## Bump version

```bash
sed -i -e 's/1.3.0/1.3.1/' \
    Makefile.inc src/lib/Cargo.toml src/python/setup.py .cargo/config.toml \
    src/python/libnmstate/__init__.py
```
