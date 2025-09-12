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
Is able to get the tools pretty consistently.
Tasks are too granular. 
- Assumes each code block is a task.
- We can use markdown formatting to decide where to split tasks.
- We accumulate a list of tools used in each task.

V0.2
- Easier thing to test
    - Given a small list of tools and a description of a task, can the llm write code to match the tutorial?
- Tool extractor
    - Combine like tools with a unified description.
- Tool selector
    - LLM to search the tool database using vector embeddings for possible tools.
- Task generator
    - Split tutorial files based on markdown formatting into reference tasks.
    - A task includes a task id, a concise text description, a list of referrenced tools, and an example of code that fullfills the task.
    - We can ask an llm to generate novel tasks based on reference tasks.
- Evaluation and loss
    - Deterministic
        - A1 Syntax/run-time errors
            - Binary 0, 1
        - A2 Compare tutorial's expected result
            - Numeric: scale by tolerance
            - Text: fuzzy string match
        - A3 Tool call trace
            - Jaccard similarity between predicted vs. reference tool sets (0–1)
    - LLM as a judge
        - B1 Approach soundness: “Given the tutorial intent, is the strategy appropriate?” (yes/no)
        - B2 Tool appropriateness: “Are these tools reasonable alternatives for this task?” (yes/no)
        - B3 Result plausibility: “Does the observed output plausibly satisfy the described goal?” (yes/no)
        - B Reward is just weighted mean of these three scores.
    - Efficiency
        - C1 Step cost penalty: Normalize by reference steps: penalty = min(1, steps / steps_ref), then subtract α·penalty.
    - Reward is just weighted sum of these three components, gated by A1
        - reward = A1 * (wa2 * A2 + wa3 * A3 + wB * B + wC1 * C1)

