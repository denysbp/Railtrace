# How I Used AI

Before starting any project, I always try to understand the problem, the business rules and the possible solutions. Normally, this process of analysis and understanding takes some time, but in this project I had a tighter deadline than I am used to.

Therefore, my first decision was to define how I would use AI, taking into account the limitations of prompts and available tokens.

I decided to use three AI tools, each with a specific role:

- **ChatGPT — Assistant and advisor:** it was the only tool that had knowledge of the entire project context, including the challenge, the business rules and the requirements. I used it to present my reasoning, discuss architecture and modelling decisions and get feedback, ensuring that the solutions respected all the rules.
- **Claude Code — Implementer:** I used it to implement code based on the instructions I provided. Its role was to carry out the requested tasks and leave comments when necessary, without making architecture or business decisions on its own. Whenever it did, I rejected those changes.
- **GitHub Copilot — Tester:** I used it to analyse the code and help create and run tests.

Although I used three AI tools, only one had knowledge of the full project context: ChatGPT. Claude Code received specific instructions for each task, while GitHub Copilot focused on code analysis and tests.

On my part, I wrote some parts of the code directly, namely the API, the `Worker` class and parts of `docker-compose.yml` and `Makefile`.

However, the architecture design, the separation of modules, the modelling decisions and the technical decisions were my responsibility. I sought to use AI as a tool to support implementation and validation, always maintaining control over the decisions made throughout development.
