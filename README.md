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
Use AST to parse exposed tools (functions, classes, apis)
- Assumes code is simple (Doesn't consider re-exports, decorator effects, and dynamic constructs)
Locate tutorials and parse a list of tasks using llm and regex and ast
- Assume tutorials are all in jupyter notebooks.
- Assumes markdown before code block is the only necessary context
- Also when we extract from the jupyter notebook, we assume each block has its own imports.

V0.1
Tool extractor now has an llm that crawls through readmes and adds to the tools.json
- This is useful for submodules and aliases that aren't caputred by the ast like sc.pp.*
- Account for re-exports
Task extractor now has a notebook level import map.
- This is necessary since units are often run in sequence and may have dependencies.
- Clean python code (get rid of ipython stuff)

Results:
Is able to get the tools pretty consistently
Tasks are too granular. 
- Assumes each code block is a task.
- We can use markdown formatting to decide where to split tasks.
- We accumulate a list of tools used in each task

V0.2
- Add definition for loss function

Executor
Define reward function. What do we care about?
- Chosen tools are correct
- They are used in the correct way
- Since we are evaluating tutorials, the answer should be pretty similar to the expected answer.
- Output of the tool is also matching the tutorial
