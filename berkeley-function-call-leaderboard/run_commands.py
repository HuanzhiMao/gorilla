import subprocess
from itertools import product

model_threads = {
    "gpt-4o-mini-2024-07-18": 20,
    # "gpt-4o-2024-11-20": 20,
    "claude-3-5-haiku-20241022": 5,
    # "claude-3-7-sonnet-20250219": 5,
    "grok-3-mini-beta": 20,
    "mistral-large-2411": 2
}

test_categories = "simple,parallel,multiple,live_simple,live_parallel,live_multiple"
return_formats = ["json", "python", "verbose_xml", "concise_xml"]
function_doc_formats = ["json", "python", "xml"]
has_tool_call_tag_options = ["True", "False"]

# Generate all combinations
prompt_variations = [
    f"return_format={r},function_doc_format={f},has_tool_call_tag={t}"
    for r, f, t in product(return_formats, function_doc_formats, has_tool_call_tag_options)
]

# Run BFCL commands
for model, threads in model_threads.items():
    for variation in prompt_variations:
        cmd = [
            "bfcl", "generate",
            "--model", model,
            "--test-category", test_categories,
            "--prompt-variation", variation,
            "--num-threads", str(threads)
        ]

        print(f"\n🔹 Running: {' '.join(cmd)}\n")
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed: {e}")

# After all runs, git commit and push
print("\n✅ All jobs finished. Committing results to Git...\n")
try:
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "add results"], check=True)
    subprocess.run(["git", "push"], check=True)
    print("✅ Git push completed.")
except subprocess.CalledProcessError as e:
    print(f"❌ Git operation failed: {e}")
