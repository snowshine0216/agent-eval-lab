# Twelve-Week Roadmap

The roadmap prioritizes job-relevant Agent Evaluation evidence. Software
architecture, functional programming, testing, and statistics are learned by
applying them to the project rather than studying them in isolation.

## Time Allocation

- 65%: build and analyze Agent Evaluation systems;
- 25%: apply software engineering fundamentals;
- 10%: build statistical foundations.

## Weeks 1-2: Minimum Evaluation System

Deliver:

- an initial task schema;
- 20 tasks covering tool use, multi-turn instructions, and small coding tasks;
- a Python evaluation runner;
- deterministic graders;
- a baseline report.

Engineering focus:

- dependency boundaries;
- pure core and effectful edges;
- actions, calculations, and data.

## Weeks 3-4: Dataset and Grader Quality

Deliver:

- a task taxonomy and scoring rubric;
- 50 reviewed tasks;
- an initial model-based grader;
- a human-versus-model grader agreement check;
- a failure-mode report;
- a comparison of two agent configurations.

Statistics focus:

- probability and random variables;
- expectation and variance;
- estimators and confidence intervals.

## Weeks 5-6: Coding Agent Evaluation

Deliver:

- 10-20 small code-repair tasks;
- test-execution graders;
- isolated, reproducible task environments;
- explicit classification of task, agent, and harness failures.

Engineering focus:

- test-driven development;
- boundary and integration testing;
- reproducibility.

## Weeks 7-8: Controlled Experiment

Run a pre-specified experiment such as:

> Does a more precise tool description improve tool-selection accuracy?

Deliver:

- hypothesis and metric definitions;
- development and held-out splits;
- repeated trials;
- uncertainty estimates;
- trace-based failure analysis.

Statistics focus:

- hypothesis testing;
- bootstrap confidence intervals;
- regression fundamentals;
- multiple-testing risk.

## Weeks 9-10: Multi-Turn Failure Modes

Add tasks for:

- incorrect tool selection;
- incorrect argument extraction;
- premature termination;
- repeated or looping actions;
- forgotten earlier instructions;
- failure recovery;
- grader exploitation.

Deliver a report explaining how to distinguish agent limitations from
evaluation-system defects.

## Weeks 11-12: Portfolio Release

Deliver:

- a clear README and architecture diagram;
- dataset documentation;
- reproducible experiment commands;
- CI and automated tests;
- two controlled experiments;
- a failure-mode analysis;
- known limitations;
- a technical article in English or Chinese.

## Reading Applied to the Project

- *Clean Architecture*: boundaries and dependency direction;
- *Grokking Simplicity*: pure calculations, actions, and immutable data;
- *Test-Driven Development by Example*: red-green-refactor delivery;
- *All of Statistics*: uncertainty and experimental reasoning.

*Advances in Financial Machine Learning* and *Fundamentals of Software
Architecture* are intentionally deferred until the initial portfolio milestone
is complete.
