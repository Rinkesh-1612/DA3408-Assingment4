# AI Disclosure

DA3408 Assignment 4. Rinkesh (DA24B017).

## 1. Tool

I used **Claude Code** for this assignment. Claude Code is a command-line coding assistant from Anthropic.
The session used the models Opus 5.5 and Sonnet 5.5.

## 2. What Claude Code did

| No. | Task | Result |
|---|---|---|
| 1 | Gave me templates of the Python files. | The first version of the Python code. |
| 2 | Wrote the dashboard generator `scripts/gen_dashboard.py`. | The file `dashboards/captioning.json`. |
| 3 | Changed the user interface of the Streamlit app. | A plain-language introduction, a sidebar and help text. |
| 4 | Wrote the `Makefile`. | Short commands for the long Docker and script commands. |
| 5 | Edited `README.md`. | A clear layout and correct formatting. |
| 6 | Polished this disclosure. | This file. |
| 7 | Helped me keep the repository structure. | The folders `src`, `configs`, `dashboards` and `scripts`. |

## 3. Model in the application

The application uses the model `Salesforce/blip-image-captioning-base`.
This model is part of the application. It is not an AI helper.
The model runs on the CPU. The application sends no data to an AI service.
