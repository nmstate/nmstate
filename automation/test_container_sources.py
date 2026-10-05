# SPDX-License-Identifier: Apache-2.0

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "automation/tests-container-utils.sh"
IPSEC = ROOT / "tests/integration/testlib/ipsec.py"
INTERNAL_IMAGE = "registry.example.org/nmstate/dev@sha256:" + "a" * 64


def stub(argv="sys.argv[1:]"):
    return (
        f"#!{sys.executable} -IS\n"
        "import json, os, sys\n"
        "with open(os.environ['COMMAND_LOG'], 'a') as log:\n"
        f"    log.write(json.dumps({argv}) + '\\n')\n"
    )


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="nmstate-sources-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.log = self.directory / "commands.jsonl"
        self.env = dict(os.environ)
        for name in tuple(self.env):
            if name.startswith("GIT_"):
                self.env.pop(name)
        for name in (
            "CONTAINER_IMAGE",
            "NMSTATE_REPO",
            "NMSTATE_SKIP_IMAGE_REBUILD",
            "NMSTATE_IPSEC_IMAGE",
            "BRANCH_NAME",
            "RUN_BAREMETAL",
            "debug_exit_shell",
            "FAIL_PULL",
            "PULL_FAILURES",
            "BUILD_EXIT",
        ):
            self.env.pop(name, None)
        config = self.directory / "gitconfig"
        config.write_text("")
        self.env.update(
            COMMAND_LOG=str(self.log),
            CONTAINER_CMD=str(self.bin / "podman"),
            PROJECT_PATH=str(self.directory),
            CONTAINER_IMAGE=INTERNAL_IMAGE,
            GIT_CONFIG_GLOBAL=str(config),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_ALLOW_PROTOCOL="file",
        )
        self.write_command(
            "podman",
            stub() + "if sys.argv[1] == 'run': print('test-container')\n"
            "if sys.argv[1] == '--version': print('podman test stub')\n"
            "if sys.argv[1] == 'pull':\n"
            "    with open(os.environ['COMMAND_LOG']) as log:\n"
            "        calls = [json.loads(line)[0] for line in log]\n"
            "    attempts = calls.count('pull')\n"
            "    if attempts <= int(os.environ.get('PULL_FAILURES', '0')):\n"
            "        sys.exit(1)\n"
            "    sys.exit(int(os.environ.get('FAIL_PULL', '0')))\n",
        )

    def write_command(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    def reset_log(self):
        if self.log.exists():
            self.log.unlink()

    def calls(self, kind=None):
        if not self.log.exists():
            return []
        calls = [
            json.loads(line) for line in self.log.read_text().splitlines()
        ]
        return [call for call in calls if kind in (None, call[0])]

    def execute(self, argv, cwd):
        return subprocess.run(
            argv,
            cwd=cwd,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=20,
        )

    def shell(self, code, cwd=None):
        return self.execute(
            [
                "bash",
                "-e",
                "-c",
                f"source {shlex.quote(str(HELPERS))}\n{code}",
            ],
            cwd or self.directory,
        )

    def test_prebuilt_image_bypasses_git_and_preserves_digest(self):
        self.env["NMSTATE_SKIP_IMAGE_REBUILD"] = "1"
        result = self.shell("git() { return 99; }; rebuild_container_images")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [["pull", INTERNAL_IMAGE]])

    def test_container_command_prefix(self):
        self.env["NMSTATE_SKIP_IMAGE_REBUILD"] = "1"
        self.env["CONTAINER_CMD"] = "env " + self.env["CONTAINER_CMD"]
        result = self.shell("rebuild_container_images")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [["pull", INTERNAL_IMAGE]])

    def test_exhausted_pull_stops_before_container_creation(self):
        marker = self.directory / "container-created"
        self.env.update(
            NMSTATE_SKIP_IMAGE_REBUILD="1",
            FAIL_PULL="1",
            CI="true",
            CONTAINER_CREATED=str(marker),
        )
        result = self.shell(
            'create_container() { : > "$CONTAINER_CREATED"; }; '
            "if container_pre_test_setup; then exit 0; else exit $?; fi"
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(marker.exists())
        pulls = self.calls("pull")
        self.assertEqual(len(pulls), 5)

    def test_transient_outer_pull_recovers(self):
        self.env.update(NMSTATE_SKIP_IMAGE_REBUILD="1", PULL_FAILURES="2")
        result = self.shell("rebuild_container_images")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls(), [["pull", INTERNAL_IMAGE]] * 3)

    def local_baseline(self):
        repo = self.directory / "local mirror"
        repo.mkdir()

        def git(*args):
            result = self.execute(["git", *args], repo)
            self.assertEqual(result.returncode, 0, result.stderr)

        git("init")
        git("checkout", "-b", "base")
        (repo / "packaging").mkdir()
        fixture = repo / "packaging" / "fixture"
        fixture.write_text("base\n")
        git("add", ".")
        git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.org",
            "commit",
            "-m",
            "baseline",
        )
        self.env["NMSTATE_REPO"] = str(repo)
        return repo, fixture

    def test_local_baseline_and_failed_fetch_with_stale_fetch_head(self):
        repo, fixture = self.local_baseline()
        code = "if is_file_changed packaging; then exit 0; else exit $?; fi"
        self.assertEqual(self.shell(code, repo).returncode, 1)
        fixture.write_text("changed\n")
        self.assertEqual(self.shell(code, repo).returncode, 0)
        self.env["NMSTATE_REPO"] = str(self.directory / "missing")
        self.assertEqual(self.shell(code, repo).returncode, 2)
        self.assertEqual(self.calls(), [])

    def check_changed_packaging_build(self, build_exit):
        repo, fixture = self.local_baseline()
        fixture.write_text("changed\n")
        (repo / "packaging" / "Dockerfile.c9s-nmstate-dev").touch()
        self.write_command(
            repo / "packaging" / "build-container.sh",
            stub("['build', *sys.argv[1:]]")
            + "sys.exit(int(os.environ['BUILD_EXIT']))\n",
        )
        marker = self.directory / "container-created"
        self.env.update(
            PROJECT_PATH=str(repo),
            CONTAINER_IMAGE="quay.io/nmstate/c9s-nmstate-dev",
            BUILD_EXIT=str(build_exit),
            CONTAINER_CREATED=str(marker),
            CI="true",
        )
        result = self.shell(
            'create_container() { : > "$CONTAINER_CREATED"; }; '
            "container_exec() { :; }; container_pre_test_setup",
            cwd=repo,
        )
        self.assertEqual(result.returncode, build_exit, result.stderr)
        self.assertEqual(marker.exists(), build_exit == 0)
        self.assertEqual(
            self.calls(), [["--version"], ["build", "c9s-nmstate-dev"]]
        )

    def test_changed_packaging_build_succeeds(self):
        self.check_changed_packaging_build(0)

    def test_changed_packaging_build_failure_stops_setup(self):
        self.check_changed_packaging_build(7)

    def test_changed_packaging_rejects_unbuildable_images(self):
        repo, fixture = self.local_baseline()
        fixture.write_text("changed\n")
        self.env["PROJECT_PATH"] = str(repo)
        for image in (
            INTERNAL_IMAGE,
            "registry.example.org/nmstate/c9s-nmstate-dev",
            "quay.io/nmstate/c9s-nmstate-dev@sha256:" + "d" * 64,
        ):
            with self.subTest(image=image):
                self.env["CONTAINER_IMAGE"] = image
                result = self.shell(
                    "if rebuild_container_images; then exit 0; "
                    "else exit $?; fi",
                    cwd=repo,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.calls(), [])

    def test_diff_error_is_not_treated_as_no_changes(self):
        result = self.shell(
            'git() { if [ "$1" = fetch ]; then return 0; '
            "else return 128; fi; }; "
            "if rebuild_container_images; then exit 0; else exit $?; fi"
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.calls(), [])

    def test_packaging_fetch_defaults_and_overrides(self):
        self.write_command("git", stub("['git', *sys.argv[1:]]"))
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        for repo, branch in (
            (None, None),
            ("/internal/source mirror", "stable"),
        ):
            with self.subTest(repo=repo, branch=branch):
                self.reset_log()
                if repo:
                    self.env.update(NMSTATE_REPO=repo, BRANCH_NAME=branch)
                result = self.shell("rebuild_container_images")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    self.calls()[0],
                    [
                        "git",
                        "fetch",
                        "--",
                        repo or "https://github.com/nmstate/nmstate.git",
                        "refs/heads/" + (branch or "base"),
                    ],
                )
                self.assertEqual(self.calls()[1][3], "--name-only")
                self.assertIn("FETCH_HEAD", self.calls()[1])
                self.assertEqual(self.calls()[2], ["pull", INTERNAL_IMAGE])

    def configure_runner(self):
        self.write_command("lsmod", "#!/bin/sh\necho openvswitch\n")
        self.write_command("systemctl", "#!/bin/sh\necho running\n")
        self.write_command("tput", "#!/bin/sh\necho 80\n")
        self.write_command("git", "#!/bin/sh\nexit 99\n")
        self.env.update(
            PATH=str(self.bin) + os.pathsep + self.env["PATH"],
            CI="true",
            NMSTATE_SKIP_IMAGE_REBUILD="1",
            NMSTATE_IPSEC_IMAGE=INTERNAL_IMAGE,
        )

    def run_runner(self, *options):
        return self.execute(
            [
                "bash",
                "-e",
                str(ROOT / "automation/run-tests.sh"),
                "--test-type",
                "integ_tier1",
                "--nolog",
                "--use-installed-nmstate",
                "--artifacts-dir",
                str(self.directory / "artifacts"),
                *options,
            ],
            ROOT,
        )

    def test_runner_image_selection_and_fixture_environment(self):
        self.configure_runner()
        cases = [
            ([], "quay.io/nmstate/fed-nmstate-dev:latest"),
            (["--el8"], "quay.io/nmstate/c8s-nmstate-dev"),
            (["--el9"], "quay.io/nmstate/c9s-nmstate-dev"),
            (["--centos-stream"], "quay.io/nmstate/c9s-nmstate-dev"),
            (["--el10"], "quay.io/nmstate/c10s-nmstate-dev"),
            (
                ["--el9", "--rawhide"],
                "quay.io/nmstate/fed-nmstate-dev:rawhide",
            ),
            (["--rawhide", "--fed"], "quay.io/nmstate/fed-nmstate-dev:latest"),
        ]
        cases += [(["--el9"], None)]
        for options, default in cases:
            with self.subTest(options=options, default=default):
                self.reset_log()
                if default:
                    self.env.pop("CONTAINER_IMAGE", None)
                else:
                    self.env["CONTAINER_IMAGE"] = INTERNAL_IMAGE
                result = self.run_runner(*options)
                self.assertEqual(result.returncode, 0, result.stderr)
                run = self.calls("run")[0]
                self.assertEqual(run[-1], default or INTERNAL_IMAGE)
                self.assertEqual(
                    self.calls("pull"), [["pull", default or INTERNAL_IMAGE]]
                )
        index = run.index("NMSTATE_IPSEC_IMAGE")
        self.assertEqual(run[index - 1], "-e")

    def ipsec_module(self, override=None):
        env = {} if override is None else {"NMSTATE_IPSEC_IMAGE": override}
        modules = {
            name: MagicMock()
            for name in (
                "libnmstate",
                "libnmstate.schema",
                "fixture.cmdlib",
                "fixture.veth",
            )
        }
        with patch.dict(os.environ, env, clear=True), patch.dict(
            sys.modules, modules
        ):
            spec = importlib.util.spec_from_file_location(
                "fixture.ipsec", IPSEC
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        return module

    def test_fixture_override_and_exhausted_retries(self):
        for override in (None, "", INTERNAL_IMAGE):
            with self.subTest(override=override):
                module = self.ipsec_module(override)
                image = (
                    override or "quay.io/nmstate/test-env:libreswan-srv-c10s"
                )
                module.IpsecTestEnv.prepare()
                module.exec_cmd.assert_called_once_with(
                    ["podman", "pull", image], check=True
                )
                module.exec_cmd.reset_mock()
                module.exec_cmd.side_effect = subprocess.SubprocessError(
                    "pull failed"
                )
                module.IpsecTestEnv.prepare()
                self.assertEqual(module.exec_cmd.call_count, 5)
                module.exec_cmd.reset_mock()
                with self.assertRaises(subprocess.SubprocessError):
                    module.start_ipsec_srv_container()
                startup = module.exec_cmd.call_args[0][0]
                self.assertEqual(startup[-1], image)
                self.assertIn("--pull=never", startup)

    def test_transient_fixture_pull_recovers(self):
        module = self.ipsec_module(INTERNAL_IMAGE)
        module.exec_cmd.side_effect = [
            subprocess.SubprocessError("pull failed"),
            subprocess.SubprocessError("pull failed"),
            (0, "", ""),
        ]
        module.IpsecTestEnv.prepare()
        self.assertEqual(module.exec_cmd.call_count, 3)
        for args, kwargs in module.exec_cmd.call_args_list:
            self.assertEqual(args, (["podman", "pull", INTERNAL_IMAGE],))
            self.assertEqual(kwargs, {"check": True})


if __name__ == "__main__":
    unittest.main()
