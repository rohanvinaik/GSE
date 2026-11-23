"""
Tinker Export Module

Exports GSE-curated data in format ready for Tinker API training.

Tinker (https://thinkingmachines.ai/tinker) supports:
- Supervised Learning (SL) with cross-entropy loss
- Reinforcement Learning (RL) with token-level rewards
- Mixed SL+RL training

This module creates training data compatible with Tinker's
prompt-distillation workflow.

Recommended models (from Tinker docs):
- Student: Qwen/Qwen3-8B-Base ($0.22/M tokens train)
- Teacher: Qwen/Qwen3-30B-A3B ($0.34/M tokens sample)
- Alternative: meta-llama/Llama-3.2-3B ($0.09/M tokens train)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from pathlib import Path
import json
import logging

from .corpus_scorer import DocumentScore, load_scored_corpus
from .curator import CurationResult

logger = logging.getLogger(__name__)


@dataclass
class TinkerTrainingConfig:
    """Configuration for Tinker training."""
    student_model: str = "Qwen/Qwen3-8B-Base"
    teacher_model: str = "Qwen/Qwen3-30B-A3B"
    renderer_name: str = "qwen3"
    epochs: int = 3
    batch_size: int = 32
    learning_rate: float = 1e-5
    max_tokens: int = 512
    temperature: float = 0.7
    loss_type: str = "cross_entropy"  # or "kl_divergence"

    def to_dict(self) -> Dict:
        return {
            'student_model': self.student_model,
            'teacher_model': self.teacher_model,
            'renderer_name': self.renderer_name,
            'epochs': self.epochs,
            'batch_size': self.batch_size,
            'learning_rate': self.learning_rate,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
            'loss_type': self.loss_type,
        }


@dataclass
class TinkerPrompt:
    """A training prompt for Tinker distillation."""
    prompt: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    completion: Optional[str] = None  # To be filled by teacher
    doc_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'prompt': self.prompt,
            'metadata': self.metadata,
            'completion': self.completion,
            'doc_id': self.doc_id,
        }


def export_for_tinker(
    curated_data: List[DocumentScore],
    output_dir: Path,
    config: Optional[TinkerTrainingConfig] = None,
    prompt_template: Optional[str] = None,
) -> Path:
    """
    Export curated data in Tinker training format.

    Args:
        curated_data: List of DocumentScore objects from curation
        output_dir: Directory to save training files
        config: Tinker training configuration
        prompt_template: Optional template for formatting prompts

    Returns:
        Path to prompts file
    """
    if config is None:
        config = TinkerTrainingConfig()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Default prompt template
    if prompt_template is None:
        prompt_template = "{text}"

    # Create prompts
    prompts = []
    for doc in curated_data:
        prompt_text = prompt_template.format(
            text=doc.text,
            **doc.metadata,
        )

        tinker_prompt = TinkerPrompt(
            prompt=prompt_text,
            metadata={
                'complexity': doc.complexity,
                'perplexity': doc.perplexity,
                'source': doc.metadata.get('source', 'unknown'),
            },
            doc_id=doc.doc_id,
        )
        prompts.append(tinker_prompt)

    # Save prompts
    prompts_path = output_dir / "prompts.jsonl"
    with open(prompts_path, 'w', encoding='utf-8') as f:
        for prompt in prompts:
            f.write(json.dumps(prompt.to_dict()) + '\n')

    # Save config
    config_path = output_dir / "config.json"
    with open(config_path, 'w') as f:
        json.dump(config.to_dict(), f, indent=2)

    # Save metadata
    metadata = {
        'n_prompts': len(prompts),
        'avg_complexity': sum(
            d.complexity.get('composite', 0) for d in curated_data
        ) / len(curated_data) if curated_data else 0,
        'config': config.to_dict(),
    }
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

    logger.info(f"Exported {len(prompts)} prompts to {prompts_path}")

    return prompts_path


def export_curation_result(
    result: CurationResult,
    output_dir: Path,
    config: Optional[TinkerTrainingConfig] = None,
) -> Path:
    """Export a CurationResult for Tinker training."""
    return export_for_tinker(
        result.documents,
        output_dir,
        config,
    )


def create_tinker_training_script(
    output_dir: Path,
    config: TinkerTrainingConfig,
) -> Path:
    """
    Generate a Python script for running Tinker training.

    This creates a runnable script that uses the Tinker API
    to train a student model on GSE-curated data.
    """
    script = f'''"""
GSE-Curated Model Training via Tinker API

This script trains a student model on GSE-curated data using
prompt distillation from a teacher model.

Generated for Experiment 3: Semantic Data Curation
"""

import json
from pathlib import Path

# Tinker imports
import tinker
from tinker import types

# Training configuration
STUDENT_MODEL = "{config.student_model}"
TEACHER_MODEL = "{config.teacher_model}"
RENDERER_NAME = "{config.renderer_name}"
EPOCHS = {config.epochs}
BATCH_SIZE = {config.batch_size}
MAX_TOKENS = {config.max_tokens}
TEMPERATURE = {config.temperature}


def load_prompts(prompts_path: Path):
    """Load training prompts from JSONL file."""
    prompts = []
    with open(prompts_path) as f:
        for line in f:
            prompts.append(json.loads(line))
    return prompts


def train_gse_curated_student(prompts_path: Path):
    """
    Train student on GSE-curated data via Tinker API.

    Step 1: Generate teacher completions for curated prompts
    Step 2: Train student via supervised learning (cross-entropy)
    """
    # Initialize Tinker clients
    service = tinker.ServiceClient()
    training_client = service.create_training_client(base_model=STUDENT_MODEL)
    sampling_client = service.create_sampling_client(base_model=TEACHER_MODEL)

    # Set up renderer
    from tinker_cookbook import renderers
    from tinker_cookbook.tokenizer_utils import get_tokenizer

    tokenizer = get_tokenizer(STUDENT_MODEL)
    renderer = renderers.get_renderer(name=RENDERER_NAME, tokenizer=tokenizer)

    # Load prompts
    prompts = load_prompts(prompts_path)
    print(f"Training on {{len(prompts)}} GSE-curated documents")
    print(f"Student: {{STUDENT_MODEL}}, Teacher: {{TEACHER_MODEL}}")

    # Training loop
    for epoch in range(EPOCHS):
        print(f"\\nEpoch {{epoch + 1}}/{{EPOCHS}}")

        for i in range(0, len(prompts), BATCH_SIZE):
            batch = prompts[i:i + BATCH_SIZE]

            # Build messages for teacher
            messages_batch = [
                [renderers.Message(role="user", content=p["prompt"])]
                for p in batch
            ]

            # Generate teacher responses
            teacher_responses = []
            for messages in messages_batch:
                model_input = renderer.build_generation_prompt(messages)
                response = sampling_client.sample(
                    prompt=model_input,
                    num_samples=1,
                    sampling_params=types.SamplingParams(
                        max_tokens=MAX_TOKENS,
                        temperature=TEMPERATURE,
                    )
                )
                teacher_responses.append(response.sequences[0].tokens)

            # Build supervised examples and train
            for messages, teacher_tokens in zip(messages_batch, teacher_responses):
                response_text = tokenizer.decode(teacher_tokens)
                full_messages = messages + [
                    renderers.Message(role="assistant", content=response_text)
                ]

                tokens, weights = renderer.build_supervised_example(full_messages)

                training_client.forward_backward(
                    tokens=tokens,
                    weights=weights,
                    loss_type="cross_entropy"
                )

            # Optimizer step
            training_client.optim_step()

            if (i // BATCH_SIZE) % 10 == 0:
                print(f"  Batch {{i // BATCH_SIZE}}/{{len(prompts) // BATCH_SIZE}}")

    # Save checkpoint
    checkpoint_path = training_client.save_state()
    print(f"\\nSaved checkpoint: {{checkpoint_path}}")
    return checkpoint_path


def evaluate_checkpoint(checkpoint_path: str):
    """Evaluate trained checkpoint on standard benchmarks."""
    import subprocess

    tasks = [
        "inspect_evals/mmlu_0_shot",
        "inspect_evals/gsm8k",
        "inspect_evals/arc_challenge",
        "inspect_evals/ifeval",
    ]

    cmd = [
        "python", "-m", "tinker_cookbook.eval.run_inspect_evals",
        f"model_path={{checkpoint_path}}",
        f"model_name={{STUDENT_MODEL}}",
        f"tasks={{','.join(tasks)}}",
        f"renderer_name={{RENDERER_NAME}}",
    ]

    print(f"\\nRunning evaluations...")
    subprocess.run(cmd)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Train model on GSE-curated data via Tinker"
    )
    parser.add_argument(
        "--prompts",
        type=Path,
        default=Path("prompts.jsonl"),
        help="Path to prompts JSONL file"
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run evaluation after training"
    )
    args = parser.parse_args()

    checkpoint = train_gse_curated_student(args.prompts)

    if args.evaluate:
        evaluate_checkpoint(checkpoint)
'''

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    script_path = output_dir / "train_gse_curated.py"
    with open(script_path, 'w') as f:
        f.write(script)

    logger.info(f"Generated training script: {script_path}")

    return script_path


def generate_experiment3_suite(
    scored_corpus_path: Path,
    output_dir: Path,
    fractions: List[float] = [0.01, 0.05, 0.10],
) -> Dict[str, Path]:
    """
    Generate complete Experiment 3 training data suite.

    Creates curated datasets for each condition:
    - random_1pct, random_5pct, random_10pct
    - perplexity_1pct, perplexity_5pct, perplexity_10pct
    - gse_complexity_1pct, gse_complexity_5pct, gse_complexity_10pct
    - gse_perplexity_1pct, gse_perplexity_5pct, gse_perplexity_10pct

    Args:
        scored_corpus_path: Path to pre-scored corpus
        output_dir: Base output directory
        fractions: Fractions to test

    Returns:
        Dict of condition_name -> prompts_path
    """
    from .curator import SemanticCurator, CurationMethod, run_curation_comparison

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run curation comparison
    results = run_curation_comparison(
        scored_corpus_path,
        output_dir / "curated",
        fractions,
    )

    # Export each condition for Tinker
    prompts_paths = {}
    config = TinkerTrainingConfig()

    for fraction_key, methods in results.items():
        for method_name, result in methods.items():
            condition_name = f"{method_name}_{fraction_key}"
            condition_dir = output_dir / "tinker" / condition_name

            prompts_path = export_curation_result(
                result,
                condition_dir,
                config,
            )

            prompts_paths[condition_name] = prompts_path

    # Generate training script
    create_tinker_training_script(
        output_dir / "tinker",
        config,
    )

    # Generate experiment summary
    summary = {
        'conditions': list(prompts_paths.keys()),
        'fractions': fractions,
        'config': config.to_dict(),
        'prompts_paths': {k: str(v) for k, v in prompts_paths.items()},
    }

    with open(output_dir / "experiment3_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"Generated Experiment 3 suite with {len(prompts_paths)} conditions")

    return prompts_paths


def estimate_tinker_cost(
    n_documents: int,
    avg_tokens_per_doc: int = 500,
    config: Optional[TinkerTrainingConfig] = None,
) -> Dict[str, float]:
    """
    Estimate Tinker API costs for training.

    Based on Tinker pricing (as of Dec 2024):
    - Qwen3-8B-Base training: $0.22/M tokens
    - Qwen3-30B-A3B sampling: $0.34/M tokens

    Args:
        n_documents: Number of training documents
        avg_tokens_per_doc: Average tokens per document
        config: Training configuration

    Returns:
        Dict with cost breakdown
    """
    if config is None:
        config = TinkerTrainingConfig()

    # Token counts
    total_tokens = n_documents * avg_tokens_per_doc

    # Teacher sampling cost
    teacher_tokens = total_tokens  # One pass for completion generation
    teacher_cost_per_m = 0.34  # Qwen3-30B-A3B
    teacher_cost = (teacher_tokens / 1_000_000) * teacher_cost_per_m

    # Student training cost
    student_tokens = total_tokens * config.epochs * 2  # Forward + backward per epoch
    student_cost_per_m = 0.22  # Qwen3-8B-Base
    student_cost = (student_tokens / 1_000_000) * student_cost_per_m

    # Evaluation cost (estimate)
    eval_tokens = 1_000_000  # ~1M tokens for standard evals
    eval_cost = (eval_tokens / 1_000_000) * student_cost_per_m

    return {
        'n_documents': n_documents,
        'total_tokens': total_tokens,
        'teacher_sampling_cost': round(teacher_cost, 2),
        'student_training_cost': round(student_cost, 2),
        'evaluation_cost': round(eval_cost, 2),
        'total_estimated_cost': round(teacher_cost + student_cost + eval_cost, 2),
        'cost_per_document': round(
            (teacher_cost + student_cost + eval_cost) / max(1, n_documents),
            4
        ),
    }
