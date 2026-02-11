# TestExplora

This repository is the official implementation of the paper "TestExplora: Benchmarking LLMs for Proactive Bug Discovery via Repository-Level Test Generation" It can be used for baseline evaluation using the prompts mentioned in the paper.

## Table of Contents

- [What is TestExplora](#what-is-testexplora)
- [Setup](#setup)
- [How to Deploy TestExplora](#how-to-deploy-testexplora)
  - [Test Generation (Inference)](#test-generation-inference)
  - [Supported Models](#supported-models)
- [Build Benchmark](#build-benchmark)
- [Contributing](#contributing)
- [Trademarks](#trademarks)

## What is TestExplora

TestExplora is a systematic, repository-level benchmark designed to evaluate the capability of Large Language Models to proactively discover latent software defects by generating tests. It was developed to evaluate the proactive defect discovery capabilities of LLMs at the repository level. 

Our dataset is constructed from real-world GitHub pull requests, containing 2,389 test-generation tasks sourced from 1,552 PRs across 482 repositories. Each task is designed such that the model must write test cases capable of triggering a Fail-to-Pass transition between buggy and repaired versions – reflecting true defect detection rather than passive confirmation. The benchmark further includes automatically generated documentation for test entry points to enable scalable evaluation.

## Setup

### Prerequisites

- Python 3.10+
- Docker (for local test evaluation)
- Git

### Installation

```bash
git clone https://github.com/microsoft/TestExplora.git
cd TestExplora
```

Install core dependencies:

```bash
pip install -r requirements.txt
```

## How to Deploy TestExplora

### Test Generation (Inference)

The main entry point is `testexplora/harness/inference.py`. Given the benchmark dataset (JSON format), it drives the target LLM to generate test cases for each task and saves the results as test patches.

```bash
python testexplora/harness/inference.py \
  --data_path <path_to_data.json> \
  --repo_testbed_dir <output_directory> \
  --model <model_name> \
  --test_type <whitebox|graybox|blackbox> \
```

#### Output

- `test_patches.json` — Generated test patches per repository and PR.
- `config.yaml` — Experiment configuration for reproducibility.
- `generation.log` — Detailed execution log.
- `trajectory/` — Agent trajectory files (for agent-based models).

### Supported Models

The benchmark supports evaluation across a broad set of LLMs and coding agents. To reproduce or customize results for a specific model, modify the corresponding call file under `testexplora/harness/call_pipeline/`.

**API-based Models (Direct LLM Call)**

| Model Key | Call File |
|---|---|
| `gpt-4o`, `o3-mini`, `o4-mini`, `gpt-5-mini`, `gpt-5`, `r1` | `call_gpt.py` |
| `claude_sonnet` | `call_gpt.py` (Anthropic via Azure) |
| `gemini-2.5-pro`, `gemini-2.5-flash` | `call_gemini.py` |
| `Codellama-34B`, `Qwen3-Coder-30B` | `call_vllm.py` |

**Agent-based Models (Agentic Code Exploration)**

| Model Key | Call File |
|---|---|
| `sweagent-*` | `call_sweagent.py` |
| `traeagent-*` | `call_traeagent.py` |

> **Note:** Agent-based models only support `whitebox` test type.

## Build Benchmark

To construct a benchmark dataset similar to TestExplora from your own set of GitHub repositories, use `testexplora/build_benchmark/process_data.py`. It automates the end-to-end pipeline:

1. **Clone repositories** and iterate over closed pull requests.
2. **Checkout the base commit** (pre-PR state) and extract code structure & dependency graphs.
3. **Apply the PR patch**, then re-extract code structure to obtain the post-PR state.
4. **Identify changed functions/methods** by mapping diff line ranges to AST-level code elements.

```bash
python testexplora/build_benchmark/process_data.py
```

> Before running, update the paths at the bottom of `process_data.py` to point to your repository data JSON directory and a local directory for cloning repos.

The script relies on two helper modules under the same directory:

- **`parse_repo.py`** — AST-based extraction of classes, functions, methods, and their metadata from a Python repository.
- **`build_dependency_graph.py`** — Builds inter-function dependency graphs using NetworkX, including cross-file import resolution.

## Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.opensource.microsoft.com.

When you submit a pull request, a CLA bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., status check, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.

## Trademarks

This project may contain trademarks or logos for projects, products, or services. Authorized use of Microsoft 
trademarks or logos is subject to and must follow 
[Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general).
Use of Microsoft trademarks or logos in modified versions of this project must not cause confusion or imply Microsoft sponsorship.
Any use of third-party trademarks or logos are subject to those third-party's policies.
