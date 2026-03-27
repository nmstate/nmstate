# NMstate Project Governance

The NMstate project is dedicated to creating a declarative network management
API for hosts. NMstate provides a library with an accompanying command line tool
that manages host networking settings in a declarative manner using a
pre-defined schema. The project focuses on providing enterprise-grade networking
management through a northbound declarative API with multi-provider support.

This governance explains how the project is run.

- [Values](#values)
- [Maintainers](#maintainers)
  - [Becoming a Maintainer](#becoming-a-maintainer)
  - [Removing a Maintainer](#removing-a-maintainer)
- [Meetings](#meetings)
- [Code of Conduct](#code-of-conduct)
- [Security Response](#security-response)
- [Voting](#voting)
- [Modifying this Charter](#modifying-this-charter)

## Values

The NMstate project and its leadership embrace the following values:

- Openness: Communication and decision-making happens in the open and is
  discoverable for future reference. As much as possible, all discussions and
  work take place in public forums and open repositories, including GitHub,
  the [#nmstate](https://cloud-native.slack.com/archives/nmstate) channel on
  [CNCF Slack](https://slack.cncf.io), and the
  [#nmstate:fedora.im](https://matrix.to/#/#nmstate:fedora.im) Matrix channel.

- Fairness: All stakeholders have the opportunity to provide feedback and submit
  contributions, which will be considered on their merits.

- Community over Product or Company: Sustaining and growing our community takes
  priority over shipping code or sponsors' organizational goals. Each
  contributor participates in the project as an individual.

- Inclusivity: We innovate through different perspectives and skill sets, which
  can only be accomplished in a welcoming and respectful environment.

- Participation: Responsibilities within the project are earned through
  participation, and there is a clear path up the contributor ladder into
  leadership positions.

## Maintainers

NMstate Maintainers have write access to the
[project GitHub repository](https://github.com/nmstate/nmstate). They can merge
their own patches or patches from others. The current Maintainers can be found
in [MAINTAINERS.md](./MAINTAINERS.md). Maintainers collectively manage the
project's resources and contributors.

This privilege is granted with some expectation of responsibility: Maintainers
are people who care about the NMstate project and want to help it grow and
improve. A Maintainer is not just someone who can make changes, but someone who
has demonstrated their ability to collaborate with the team, get the most
knowledgeable people to review code and docs, contribute high-quality code, and
follow through to fix issues (in code or tests).

A Maintainer is a contributor to the project's success and a citizen helping
the project succeed.

The collective team of all Maintainers is known as the Maintainer Council, which
is the governing body for the project.

### Becoming a Maintainer

To become a Maintainer you need to demonstrate the following:

- commitment to the project:
  - participate in discussions, contributions, code and documentation reviews
    for 10 months or more,
  - perform reviews for 10 non-trivial pull requests,
  - contribute 15 non-trivial pull requests and have them merged,
- ability to write quality code and/or documentation,
- ability to collaborate with the team,
- understanding of how the team works (policies, processes for testing and code
  review, etc),
- understanding of the project's code base and coding and documentation style.

A new Maintainer must be proposed by an existing Maintainer by opening a pull
request against [MAINTAINERS.md](./MAINTAINERS.md). A simple majority vote of
existing Maintainers approves the application via PR review. Maintainers
nominations will be evaluated without prejudice to employer or demographics.

Maintainers who are selected will be granted the necessary GitHub rights.

### Removing a Maintainer

Maintainers may resign at any time if they feel that they will not be able to
continue fulfilling their project duties.

Maintainers may also be removed after being inactive, failure to fulfill their
Maintainer responsibilities, violating the Code of Conduct, or other reasons.
Inactivity is defined as a period of very low or no activity in the project
for a year or more, with no definite schedule to return to full Maintainer
activity.

A Maintainer may be removed at any time by a 2/3 vote of the remaining
Maintainers.

Depending on the reason for removal, a Maintainer may be converted to Emeritus
status. Emeritus is a purely representative role recognizing past contributions.
Emeritus Maintainers hold no project privileges or responsibilities, but can be
returned to Maintainer status through the standard nomination process if their
availability changes.

## Meetings

There are currently no regular project meetings. Maintainers may schedule
ad-hoc meetings as needed. Day-to-day communication happens on the
[#nmstate](https://cloud-native.slack.com/archives/nmstate) channel on
[CNCF Slack](https://slack.cncf.io) and the
[#nmstate:fedora.im](https://matrix.to/#/#nmstate:fedora.im) Matrix channel.

Maintainers will have closed meetings in order to discuss security reports
or Code of Conduct violations. Such meetings should be scheduled by any
Maintainer on receipt of a security issue or CoC report. All current Maintainers
must be invited to such closed meetings, except for any Maintainer who is
accused of a CoC violation.

## Code of Conduct

[Code of Conduct](./CODE_OF_CONDUCT.md) violations by community members will be
discussed and resolved by the Maintainer Council.

## Security Response

All Maintainers are collectively responsible for handling security reports
according to the [security policy](./SECURITY.md).

## Voting

While most business in NMstate is conducted by
"[lazy consensus](https://community.apache.org/committers/lazyConsensus.html)",
periodically the Maintainers may need to vote on specific actions or changes.
A vote can be taken via a GitHub issue. Any Maintainer may demand a vote be
taken.

Most votes require a simple majority of all Maintainers to succeed, except where
otherwise noted. Two-thirds majority votes mean at least two-thirds of all
existing Maintainers.

## Modifying this Charter

Changes to this Governance and its supporting documents may be approved by
a 2/3 vote of the Maintainers.
