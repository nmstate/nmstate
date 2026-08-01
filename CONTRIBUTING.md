# Contributing to Nmstate

:+1: Thank you for contributing! :+1:

The *Nmstate* team is following the guidelines presented in this document.
These are mostly guidelines, not rules. Use your best judgment and follow
these guidelines when contributing to the project.


## Code of Conduct

This project and everyone participating in it is governed by the
[Nmstate Code of Conduct](CODE_OF_CONDUCT.md).
By participating, you are expected to uphold this code.
Please report unacceptable behavior to the nmstate team.


## How to Contribute

- Bugs: Tracked as [GitHub issues][issues].
- Enhancements: RFE suggestions are tracked as [GitHub issues][issues].
- Code: Managed on [GitHub][repo] through [Pull Requests][pulls].

### Code contributions
Contribute with bugfixes or new features via [Pull Requests][pulls].

Feel free to discuss your approach beforehand by opening an [issue][issues] or
reaching out to the maintainers in any of our [public channels](README.md#contact).

Ensure that your contribution meets these requirements in order to be considered
and merged by the maintainers:
- Follow the [Coding and Style Guidelines](#Coding-and-Style-Guidelines).
- Unit tests and integration tests pass. Run them locally as explained in
  [Running the integration tests](#running-the-integration-tests) before submitting.  
  CI jobs will be run in the Pull Request to ensure that all the tests pass. If
  any job fails, it must be fixed before merging.
- Apply the changes requested by the maintainers after their code review.


## Coding and Style Guidelines

### Rust
- Nmstate is written primarily in Rust, and its coding style should follow
  the best practices of Rust coding.
- The code style must comply with the [default Rust style][rust_style_guide]
  with very few exceptions (notably, we use 80 characters line width).
- You can use [rustfmt][rustfmt] to automatically format your code. In practice,
  it is mandatory to use it because the CI uses it to verify the code style.
- Source code must be covered by unit tests found in the `./rust/src/lib/unit_tests`
  and/or integration tests in `./tests/integration`.
- Source code must also pass the [Clippy][clippy_usage] lint check, which checks
  for common mistakes and best practices.

### Python
Our integration tests are written in Python with the `pytest` framework.
- Use the [black](https://github.com/python/black) code formatter to comply
  with the project's Python code style.
- Packages, modules, functions, methods and variables are in snake_case.
- Class names are in CamelCase.
- Imports should be grouped in the following order:
  - Standard library imports
  - Related third party imports
  - Local application-specific or library-specific imports.
- Indentation is made by 4 space characters.

### Clean Code
Do your best to follow the clean code guidelines.

- Name classes using a noun.
- Name functions/methods using a verb.
- Make them as small as possible.
- They should do one thing only and do it well.
  One thing means one level of abstraction.
  The names and code should reflect that.
- Methods/functions should be organized per level of abstraction,
  where callee sits below their caller.
- Avoid output-arguments (arguments to output data out of a function/method).
- Don’t use boolean arguments, use 2 functions/methods instead.

Ref: Book: Clean Code by Robert C. Martin (Uncle Bob)

### Write a good commit message
Here are a few rules to keep in mind while writing a commit message

   1. Separate subject from body with a blank line
   2. Limit the subject line to 50 characters
   3. Capitalize the subject line
   4. Do not end the subject line with a period
   5. Use the imperative mood in the subject line
   6. Wrap the body at 72 characters
   7. Use the body to explain what and why vs. how

 A good commit message looks something like this
```
  Summarize changes in around 50 characters or less

 More detailed explanatory text, if necessary. Wrap it to about 72 characters 
 or so. In some contexts, the first line is treated as the subject of the 
 commit and the rest of the text as the body. The blank line separating the 
 summary from the body is critical (unless you omit the body entirely); various 
 tools like `log`, `shortlog` and `rebase` can get confused if you run the two 
 together.

 Explain the problem that this commit is solving. Focus on why you are making 
 this change as opposed to how (the code explains that).
 Are there side effects or other unintuitive consequences of this change? 
 Here's the place to explain them.

 Further paragraphs come after blank lines.

  - Bullet points are okay, too

  - Typically a hyphen or asterisk is used for the bullet, preceded by a single 
    space, with blank lines in between, but conventions vary here

 If you use an issue tracker, put references to them at the bottom, like this:

 Resolves: #123
 See also: #456, #789

Do not forget to sign your commit! Use `git commit -s`
```

Rules 1, 2, 4 and 6 are enforced by
[gitlint](https://jorisroovers.com/gitlint/) in CI (see `.gitlint`);
besides a period, gitlint also rejects `!`, `,` and `;` at the end of
the subject line.
To check commit messages locally, and to run the Rust lint hooks,
install the [pre-commit](https://pre-commit.com/) hooks:

```console
pre-commit install --hook-type pre-commit --hook-type commit-msg
```

This is taken from [chris beams git commit](https://chris.beams.io/posts/git-commit/).
You may want to read this for a more detailed explanation (and links to other 
posts on how to write a good commit message). This content is licensed under 
[CC-BY-SA](https://creativecommons.org/licenses/by-sa/4.0/).


## Installing and Compiling

This guide will walk you through the process of installing and compiling nmstate from the source. For installing stable release or other installation methods, please refer to nmstate installation guide: https://nmstate.io/user/install.md

### Prerequisite 
A Linux operating system is required. For Windows or macOS users, you can set up a Linux environment using VirtualBox, VMware, or Virt-manager.

### Install Cargo Tool
Cargo is Rust's build system and package manager, necessary for working with Rust programs, such as Nmstate.
```
sudo apt update && sudo apt install cargo git # Debian/Ubuntu
```
```
sudo dnf install cargo git # Fedora, RHEL
```

### Get the Source Code
Clone the Nmstate repository: 
```
git clone https://github.com/nmstate/nmstate.git
cd nmstate
```

### Compilation
Run the following command at the top level of the code to compile the project:
```
make
```

### Running the Compiled Program
After successful compilation, you can run the nmstatectl tool to display the current network state:
```
rust/target/debug/nmstatectl show # To dump the state in json format, use the --json flag.
``` 


## Useful tips for development

### Code structure
These are the main elements of the code, placed under `./rust/src`:
- `lib`: The nmstate Rust crate. This is the main part of the project.
   - `lib/nispor`: code related to querying the network state via Nispor.
   - `lib/nm`: code related to applying the settings via NetworkManager backend.
   - `lib/ovsdb`: code related to ovsdb communication and structures.
   - `lib/policy`: the nmpolicy related code.
   - `lib/unit_tests`: unit tests.
- `cli`: The `nmstatectl` command line tool.
- `clib`: C bindings of nmstate.
- `go`: Go library of nmstate wrapping the C bindings.
- `python`: Python library of nmstate wrapping the C bindings.

Also, `./tests/integration` contains the integration tests. Every new feature
should be covered here.

Other auxiliary folders:
- `./automation`: the [automation environment](./automation/README.md), serving
  the tests of Nmstate.
- `./doc`: the man pages.
- `./examples`: YAML examples for different configurations.
- `./logo`: logos used for publication.
- `./packaging`: utilities for packaging and containers creation.

### Setting up a development environment
As nmstate modifies the host's network configuration directly, it is advisable
to test it inside a virtual machine. It is also possible to test it inside a
container, but it's not straightforward to create as it needs to have
NetworkManager running and enough privileges for certain network operations.

Most developers find it useful to have a virtual machine, sharing the project's
folder between the host and the virtual machine, so that you can modify the
code from the host and compile and run in the virtual machine.

For simple manual tests, it is also possible and easier to do them directly in
the host, if you accept the risk of messing up your network configuration. Just
build the code and execute commands with the `rust/target/debug/nmstatectl`
binary. There is no need to install it.

### Running the unit tests
Unit tests don't modify your network configuration, so they are safe to run
locally. They also run pretty fast.

```
cd rust
cargo test
```

### Running the integration tests
The most straightforward way to run the integration tests is using the
[automation/run-tests.sh script](automation/run-tests.sh). Read its documentation
in [automation/README.md](automation/README.md) or run `automation/run-tests.sh --help`.

You can also run the tests directly, but it is highly discouraged to do it
directly in your host. Better do it in a dedicated virtual machine. The tests
are executed with [pytest](https://docs.pytest.org/en/stable/how-to/usage.html).

By default, the tests will use the system installed package of nmstate. To test
nmstate from the repository, pytest needs to know how to find several things:
- The `libnmstate.so` shared library: use the `LD_LIBRARY_PATH` env variable.
- The Python bindings: use the `PYTHONPATH` env variable.
- The `nmstatectl` binary: use the `PATH` env variable.

Example commands to run the integration tests from the repository:
```
cd rust; cargo build; cd ..
sudo \
    PATH="rust/target/debug:$PATH" \
    LD_LIBRARY_PATH=rust/target/debug \
    PYTHONPATH=rust/src/python \
    pytest \
    --verbose --verbose \
    --durations=5 \
    --log-level=ERROR \
    --log-file-level=INFO \
    --log-file-format="%(asctime)s [%(levelname)8s] %(message)s (%(filename)s:%(lineno)s)" \
    --log-file-date-format="%Y-%m-%d %H:%M:%S" \
    --log-file=/tmp/pytest.log
```

Check [pytest usage how-to](https://docs.pytest.org/en/stable/how-to/usage.html)
to learn how to run only a subset of the test cases.

Note that the test suite will create at least new `eth1`, `eth2` and `eth3`
devices, so don't use those device names for anything else. It is advisable not
to have other active network devices and, if any device is needed to keep the
connectivity with the testing machine, try to use only a static IP address, as
DHCP and other dynamic addresses and routes are known to conflict with some test
cases.


<!-- links -->
[repo]: https://github.com/nmstate/nmstate
[issues]: https://github.com/nmstate/nmstate/issues
[pulls]: https://github.com/nmstate/nmstate/pulls
[rust_style_guide]: https://doc.rust-lang.org/style-guide/index.html
[rustfmt]: https://github.com/rust-lang/rustfmt
[clippy_usage]: https://doc.rust-lang.org/stable/clippy/usage.html
