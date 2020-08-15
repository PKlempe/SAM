# Contributing to SAM
❤ Thanks for taking the time to contribute to our little project. ❤

The following is a set of guidelines for contributing to this repository. These are mostly guidelines, not rules. Use your best judgment, and feel free to propose changes to this 
document in a pull request.

Here are some important resources to get you started:
* [Discord Developer Portal](https://discord.com/developers/docs/intro)
* [Discord.py documentation](https://discordpy.readthedocs.io/en/latest/)
* [Official Discord.py Discord Server](https://discord.gg/r3sSKJJ)
* [Python documentation](https://docs.python.org/)



## I've found a bug! 🐞
Great! Please ensure that the bug was not already reported by searching on GitHub under [Issues](https://github.com/PKlempe/SAM/issues).

If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/PKlempe/SAM/issues/new). Be sure to include a title, clear description and as 
much relevant information as possible. An additional step by step tutorial on how to reproduce the problem would be great, too. The issue template will generally walk you through 
the process.

### Did you write a patch that fixes a bug?
* Open a new GitHub pull request with the patch.
* Ensure the PR description clearly describes the problem and solution. Include the relevant issue number if applicable.
* Before submitting, please read the Commit & Coding Guidlines stated below.

### Did you fix whitespaces, format code, or make a purely cosmetic patch?
Changes that are cosmetic in nature and do not add anything substantial to the stability, functionality, or testability of SAM will generally not be accepted. The reason behind 
this is that someone needs to spend the time to review the patch and there might be some subtle reasons that the original code is written this way. It also pollutes the git history
which means that if someone needs to investigate a bug in the future and `git blame` these lines, they'll hit this "refactor" commit which is not very helpful.

**TL;DR:** There may be some hidden costs that are not so apparent from the surface. Please make a suggestion via `!suggest [Your Suggestion]` on the Discord Server instead.



## I've a great idea for a feature! 💡
Please submit any ideas on how to improve SAM via `!suggest [Your Suggestion]` on our Discord Server so that our users can vote on the individual suggestions. This helps us to 
find out, if there's even enough interest for a specific feature and we therefore won't waste valuable time implementing stuff that actually no one really wants.



## Submitting a Pull Request 🗳
Submitting a pull request is fairly simple, just make sure it focuses on a single aspect and doesn't manage to have [Scope Creep](https://en.wikipedia.org/wiki/Scope_creep) and 
it's probably good to go.

### Coding Guidelines
* Column limit is 120.
* Code should follow the [PEP-8 guidelines](https://www.python.org/dev/peps/pep-0008/).
* "Pythonic" design patterns should be used to the best of our knowledge.
* Code should always be checked by linters ([Pylint](https://www.pylint.org/), [MyPy](http://mypy-lang.org/)) to find errors early.
* Methods that are a part of a module API or any other type of contract, or just methods that have a high complexity, will be documented using Docstrings and [type hints](https://docs.python.org/3/library/typing.html).
* PRs have to be reviewed by at least one other contributer before merging and a merge will only be feasible if all existing tests pass. (Assuming any tests have been written).
* Defined APIs (also internal, e.g. the public methods of a module) will not be changed, only extended, except if absolutely neccessary and with the okay from the bots creators.

### Git Commit Styleguide
* Commit messages have to begin with the corresponding issue number ("#22: Fix bug" not "Fix bug")
* Use the present tense ("Add feature" not "Added feature")
  * Simple check - Complete the sentence: "This commit will ..."
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line

If you do not meet any of these guidelines, don't fret. Chances are they will be fixed upon rebasing but please do try to meet them to remove some of the workload for us.



## I'm studying Business Informatics and therefore can't code. Is there some other way I could help? 🤔
I'm glad you asked! We are always looking for people who are willing to fill our [Wiki](https://github.com/PKlempe/SAM/wiki) with content. If writing isn't your thing either, 
you can always try to get your hands on old exams/assignments and post them on our Discord Server. Even simply talking to people and convincing them to join our server would 
help us a lot.



## I'm extremely wealthy and don't know what to do with my money. Can I give you some of it? 💸
**First off**, I don't want anyone to think that they have to give me money! Even though it's true that I'm doing everything regarding the Discord Server in my spare time, this 
doesn't mean that you owe me anything. I'm doing all of this completely voluntarily and I don't expect to make any money with this.

**That being said:** If you still want to show me your appreciation by donating money to me, you can do this via the methods listed in the right side panel on the [project page](https://github.com/PKlempe/SAM).
