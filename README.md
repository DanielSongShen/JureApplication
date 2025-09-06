# JureApplication
A system that automatically extracts all tools from a GitHub repo, identifies the available tasks from its tutorials, and defines a reward function.

It needs to be able to read the code of a Github repo
Identify tools in that repo
Then read the tutorials which may be located somewhere else and identify possible tasks
Then define a reward function to evaluate the performance of the tool.

Think:
- What measurable quantity tells us that using this repo’s tools on this tutorial-task was successful, useful, or scientifically valuable?

What makes up a repo?
- Lots of infrastructure code. Some exposed functions/tools that are meant to be used. 

V0
Build high-level understanding by reading readmes and crawling through the repo. Write all findings to a document for future reference.
Use AST to parse exposed tools (functions, classes, apis)
- Assumes code is simple (Doesn't consider re-exports, decorator effects, and dynamic constructs)
Locate tutorials and parse a list of tasks using llm and regex and ast
- Assume tutorials are all in jupyter notebooks.
- Assumes markdown before code block is the only necessary context
Executor
Define reward function. What do we care about?
- Chosen tools are correct
- They are used in the correct way
- Since we are evaluating tutorials, the answer should be pretty similar to the expected answer.
- Output of the tool is also matching the tutorial

- Agent with some file navigation tools to crawl through the repo
    - Grep/regex
    - cd, ls
- Locate tutorials and read the readmes
- Acculumlate a giant doc with all the learnings
- Also find paths to relevant tools/functions