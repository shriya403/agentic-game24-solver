# Final Jury Submission Checklist

## One-time setup

- Install Python 3.10+ and Ollama.
- Run `python -m venv .venv`.
- Activate with `.venv\Scripts\activate` on Windows.
- Run `pip install -r requirements.txt`.
- Run `ollama pull qwen2.5:3b`.

## Generate final evidence

1. Start Ollama.
2. Run `python -m unittest discover -s tests -v` and capture the passing output.
3. Run `python run_experiment.py --runs 5`.
4. Confirm every saved row says `ollama` or `ollama_agentic`, not `deterministic_fallback`.
5. Launch `streamlit run app.py`.
6. Open the hard puzzle `[3,3,8,8]` and demonstrate both methods.
7. Export the benchmark CSV.

## Screenshots for the report/PPT

- Streamlit home screen with execution mode visible.
- Linear output for each puzzle.
- ToT branch table for `[3,3,8,8]`.
- Exact validator result.
- Benchmark comparison table.
- Success-rate chart.
- Latency/token chart.
- Passing unit tests.

## Scientific integrity checks

- Never call fallback numbers Qwen results.
- Never claim linear reasoning failed unless the Qwen CSV shows failure.
- Do not call the displayed arithmetic trace the model's private chain-of-thought.
- Report the same seed/model/rules for both strategies.
- Mention that ToT receives a larger search budget and measure that cost.

## Live-demo recovery

If Ollama fails during the jury, switch the Streamlit sidebar to **Deterministic fallback**. Explain that it demonstrates orchestration and exact validation, while the saved CSV contains the previously measured Qwen experiment.

