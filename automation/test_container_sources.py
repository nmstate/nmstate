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
MIRROR = "registry.example.org/mirror"


def stub(argv="sys.argv[1:]"):
    return (
        f"#!{sys.executable} -IS\n"
        "import json, os, sys\n"
        "with open(os.environ['COMMAND_LOG'], 'a') as log:\n"
        f"    log.write(json.dumps({argv}) + '\\n')\n"
    )


def pulled(module):
    return [args[0] for args, _ in module.exec_cmd.call_args_list]


class SourceTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop("NMSTATE_IMAGE_MIRROR", None)
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
            "NMSTATE_IMAGE_MIRROR",
            "BRANCH_NAME",
            "CI",
            "RUN_BAREMETAL",
            "debug_exit_shell",
            "FAIL_PULL",
            "FAIL_PULL_IMAGES",
            "FAIL_RUN",
            "PULL_FAILURES",
            "IMAGE_INSPECT_RC",
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
            stub() + "if sys.argv[1] == 'run':\n"
            "    fail_run = os.environ.get('FAIL_RUN')\n"
            "    if fail_run: sys.exit(int(fail_run))\n"
            "    print('test-container')\n"
            "if sys.argv[1] == '--version': print('podman test stub')\n"
            "if sys.argv[1:3] == ['image', 'inspect']:\n"
            "    sys.exit(int(os.environ.get('IMAGE_INSPECT_RC', '1')))\n"
            "if sys.argv[1] == 'pull':\n"
            "    failing = os.environ.get('FAIL_PULL_IMAGES', '[]')\n"
            "    if sys.argv[-1] in json.loads(failing):\n"
            "        sys.exit(1)\n"
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

    def test_explicit_images_do_not_use_mirror(self):
        self.env.update(
            NMSTATE_SKIP_IMAGE_REBUILD="1",
            NMSTATE_IMAGE_MIRROR=MIRROR,
            FAIL_PULL="1",
        )
        for image in (
            INTERNAL_IMAGE,
            MIRROR + "/c9s-nmstate-dev:latest",
            "quay.io/another-project/dev:latest",
            "quay.io/nmstate-other/dev:latest",
        ):
            with self.subTest(image=image):
                self.reset_log()
                self.env["CONTAINER_IMAGE"] = image
                result = self.shell("rebuild_container_images")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(self.calls(), [["pull", image]] * 5)

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
            NMSTATE_IMAGE_MIRROR=MIRROR,
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
            MIRROR + "/c9s-nmstate-dev",
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

    def test_upstream_mirror_is_not_retried(self):
        primary = "quay.io/nmstate/c9s-nmstate-dev"
        self.env.update(
            NMSTATE_SKIP_IMAGE_REBUILD="1",
            NMSTATE_IMAGE_MIRROR="quay.io/nmstate/",
            CONTAINER_IMAGE=primary,
            FAIL_PULL="1",
        )
        result = self.shell("rebuild_container_images")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.calls(), [["pull", primary]] * 5)

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
        self.env["NMSTATE_IMAGE_MIRROR"] = MIRROR
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
        for name in ("NMSTATE_IPSEC_IMAGE", "NMSTATE_IMAGE_MIRROR"):
            self.assertEqual(run[run.index(name) - 1], "-e")

    def test_runner_uses_mirror_after_primary_pull_failure(self):
        self.configure_runner()
        self.env["NMSTATE_IMAGE_MIRROR"] = MIRROR + "/"
        for suffix in (
            "c9s-nmstate-dev:latest",
            "c10s-nmstate-dev",
            "c9s-nmstate-dev@sha256:" + "b" * 64,
        ):
            with self.subTest(suffix=suffix):
                self.reset_log()
                primary = "quay.io/nmstate/" + suffix
                fallback = MIRROR + "/" + suffix
                self.env.update(
                    CONTAINER_IMAGE=primary,
                    FAIL_PULL_IMAGES=json.dumps([primary]),
                )
                result = self.run_runner()
                self.assertEqual(result.returncode, 0, result.stderr)
                pulls = self.calls("pull")
                self.assertEqual(
                    pulls, [["pull", primary], ["pull", fallback]]
                )
                run = self.calls("run")[0]
                self.assertEqual(run[-1], fallback)

    def test_runner_exhausts_both_sources_before_failing(self):
        self.configure_runner()
        primary = "quay.io/nmstate/c9s-nmstate-dev"
        fallback = MIRROR + "/c9s-nmstate-dev"
        self.env.update(
            CONTAINER_IMAGE=primary,
            NMSTATE_IMAGE_MIRROR=MIRROR,
            FAIL_PULL="1",
        )
        result = self.run_runner()
        self.assertNotEqual(result.returncode, 0)
        pulls = self.calls("pull")
        self.assertEqual(pulls, [["pull", primary], ["pull", fallback]] * 5)
        self.assertFalse(self.calls("run"))

    def test_failed_container_start_does_not_use_mirror(self):
        self.configure_runner()
        primary = "quay.io/nmstate/c9s-nmstate-dev"
        self.env.update(
            CONTAINER_IMAGE=primary,
            NMSTATE_IMAGE_MIRROR=MIRROR,
            FAIL_RUN="42",
        )
        result = self.run_runner()
        self.assertEqual(result.returncode, 42, result.stderr)
        pulls = self.calls("pull")
        self.assertEqual(pulls, [["pull", primary]])
        runs = self.calls("run")
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0][-1], primary)

    def test_local_images_are_preserved_and_missing_images_use_mirror(self):
        self.configure_runner()
        primary = "quay.io/nmstate/c9s-nmstate-dev"
        fallback = MIRROR + "/c9s-nmstate-dev"
        self.env.update(
            CI="false",
            CONTAINER_IMAGE=primary,
            FAIL_PULL_IMAGES=json.dumps([primary]),
        )
        for mirror, present in (("", False), (MIRROR, True), (MIRROR, False)):
            with self.subTest(mirror=mirror, present=present):
                self.reset_log()
                self.env.update(
                    NMSTATE_IMAGE_MIRROR=mirror,
                    IMAGE_INSPECT_RC="0" if present else "1",
                )
                result = self.run_runner()
                self.assertEqual(result.returncode, 0, result.stderr)
                pulls = self.calls("pull")
                needs_pull = bool(mirror and not present)
                self.assertEqual(
                    pulls,
                    (
                        [["pull", primary], ["pull", fallback]]
                        if needs_pull
                        else []
                    ),
                )
                inspections = [
                    c for c in self.calls() if c[:2] == ["image", "inspect"]
                ]
                self.assertEqual(len(inspections), bool(mirror))
                if inspections:
                    self.assertEqual(inspections[0][-1], primary)
                run = self.calls("run")[0]
                self.assertEqual(run[-1], fallback if needs_pull else primary)

    def test_nmci_wrapper_preserves_container_command(self):
        automation = self.directory / "automation"
        automation.mkdir()
        wrapper = automation / "run-tests-in-nmci.sh"
        wrapper.write_text(
            (ROOT / "automation/run-tests-in-nmci.sh").read_text()
        )
        self.write_command(
            automation / "run-tests.sh",
            stub(
                "[os.environ['CONTAINER_CMD'], os.environ['CI'],"
                " *sys.argv[1:]]"
            ),
        )
        for command in (None, "env " + str(self.bin / "podman")):
            with self.subTest(command=command):
                self.reset_log()
                self.env.pop("CONTAINER_CMD", None)
                if command:
                    self.env["CONTAINER_CMD"] = command
                result = self.execute(
                    ["bash", str(wrapper), "--el10"], self.directory
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    self.calls(),
                    [
                        [
                            command or "podman",
                            "true",
                            "--test-type",
                            "integ_tier1",
                            "--nolog",
                            "--el10",
                        ]
                    ],
                )

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

    def test_fixture_fallback_preserves_identity_and_resets_selection(self):
        for suffix in (
            "test-env:libreswan-srv-c10s",
            "test-env@sha256:" + "c" * 64,
        ):
            with self.subTest(suffix=suffix):
                primary = "quay.io/nmstate/" + suffix
                fallback = MIRROR + "/" + suffix
                module = self.ipsec_module(primary)

                def pull(command, **kwargs):
                    if command == ["podman", "pull", primary]:
                        raise subprocess.SubprocessError("primary unavailable")
                    return (0, "", "")

                module.exec_cmd.side_effect = pull
                with patch.dict(
                    os.environ, {"NMSTATE_IMAGE_MIRROR": MIRROR + "/"}
                ):
                    module.IpsecTestEnv.prepare()
                self.assertEqual(
                    pulled(module),
                    [
                        ["podman", "pull", primary],
                        ["podman", "pull", fallback],
                    ],
                )
                module.exec_cmd.reset_mock()
                module.start_ipsec_srv_container()
                startup = module.exec_cmd.call_args_list[0][0][0]
                self.assertEqual(startup[-1], fallback)
                self.assertIn("--pull=never", startup)

                module.exec_cmd.reset_mock()
                module.exec_cmd.side_effect = None
                with patch.dict(os.environ, {"NMSTATE_IMAGE_MIRROR": MIRROR}):
                    module.IpsecTestEnv.prepare()
                module.exec_cmd.assert_called_once_with(
                    ["podman", "pull", primary], check=True
                )
                module.exec_cmd.reset_mock()
                module.start_ipsec_srv_container()
                self.assertEqual(
                    module.exec_cmd.call_args_list[0][0][0][-1], primary
                )

    def test_fixture_exhausted_fallback_remains_nonfatal(self):
        primary = "quay.io/nmstate/test-env:libreswan-srv-c10s"
        fallback = MIRROR + "/test-env:libreswan-srv-c10s"
        module = self.ipsec_module(primary)
        module.exec_cmd.side_effect = subprocess.SubprocessError("unavailable")
        with patch.dict(os.environ, {"NMSTATE_IMAGE_MIRROR": MIRROR}):
            module.IpsecTestEnv.prepare()
        self.assertEqual(
            pulled(module),
            [["podman", "pull", primary], ["podman", "pull", fallback]] * 5,
        )
        module.exec_cmd.reset_mock()
        with self.assertRaises(subprocess.SubprocessError):
            module.start_ipsec_srv_container()
        self.assertEqual(module.exec_cmd.call_args[0][0][-1], primary)

    def test_fixture_explicit_image_does_not_use_mirror(self):
        module = self.ipsec_module(INTERNAL_IMAGE)
        module.exec_cmd.side_effect = subprocess.SubprocessError("unavailable")
        with patch.dict(os.environ, {"NMSTATE_IMAGE_MIRROR": MIRROR}):
            module.IpsecTestEnv.prepare()
        self.assertEqual(
            pulled(module),
            [["podman", "pull", INTERNAL_IMAGE]] * 5,
        )

    def test_fixture_upstream_mirror_is_not_retried(self):
        module = self.ipsec_module()
        module.exec_cmd.side_effect = subprocess.SubprocessError("unavailable")
        with patch.dict(
            os.environ, {"NMSTATE_IMAGE_MIRROR": "quay.io/nmstate"}
        ):
            module.IpsecTestEnv.prepare()
        self.assertEqual(
            pulled(module),
            [["podman", "pull", module.SRV_CONTAINER_IMG]] * 5,
        )


if __name__ == "__main__":
    unittest.main()
