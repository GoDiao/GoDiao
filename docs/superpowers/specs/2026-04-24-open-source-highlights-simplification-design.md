# Open Source Highlights Copy Simplification Design

## Goal
Refine the `Open Source Highlights` section in the GitHub Profile README so it presents maintained upstream projects as concise project showcases instead of detailed contribution logs.

## Why This Change
The current copy is too contribution-specific and reads like a changelog of PR work. The user wants this section to communicate:
- which open-source projects they participate in
- what each project is about
- where to click

The section should feel like project curation, not issue history.

## Current Problem
The current copy emphasizes detailed maintenance activity such as:
- encoding fixes
- Windows bugs
- config directory support
- PR numbers

That level of detail is useful in a CV or contribution list, but it is too operational for a profile README section intended to look polished and scannable.

## Design Direction
Change the section from:
- contribution-centric bullets

to:
- project-centric mini showcase blocks

Each item should contain:
1. project name
2. short official-style description
3. repository link

## Chosen Format
Use three concise bullets, each written as:
- `project name` — one or two short sentences describing the project. `Repo` link.

## Approved Copy Direction

- `paperclip` — Open-source orchestration for zero-human companies. [Repo](https://github.com/paperclipai/paperclip)
- `MiniCode` — A lightweight terminal coding assistant with Claude Code-like workflow and TUI architecture. [Repo](https://github.com/LiuMengxuan04/MiniCode)
- `investing-algorithm-framework` — Framework for developing, backtesting, and deploying automated trading algorithms and trading bots. [Repo](https://github.com/coding-kitties/investing-algorithm-framework)

## Content Rules
- no PR numbers
- no bug-fix details
- no maintenance-task wording
- no verbose explanations
- keep the section aligned with the rest of the fancy README style

## Scope
Included:
- replacing `Open Source Highlights` copy only

Not included:
- redesigning the full README again
- changing `Featured Builds`
- changing hero, toolbox, analytics, or contact sections
