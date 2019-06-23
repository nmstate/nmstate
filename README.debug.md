# Nmstate debugging

## Create debug information for libnm bugs

Run the integration tests with valgrind (it can also be used to run nmstate
directly):

```shell
G_DEBUG=fatal-warnings,gc-friendly G_SLICE=always-malloc valgrind --num-callers=100 --log-file=valgrind-log pytest tests/integration/
```

Send `valgrind-log`, core-files and Network Manager log with trace enabled to
Network Manager developers.
