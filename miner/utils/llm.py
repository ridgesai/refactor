import openai

def generate_solution_with_openai(problem_statement: str, api_key: str) -> str:
    """
    Uses OpenAI to generate a code solution for the given problem statement.
    The LLM is instructed to return only a valid unified git diff (patch), with no explanations or markdown.
    """
    client = openai.OpenAI(api_key=api_key)
    user_prompt = (
        f"{problem_statement}\n\n"
        "Output ONLY the raw unified git diff (patch) code that implements the solution. "
        "Do NOT include any explanations, markdown, code blocks, or any extra text. "
        "Do NOT use triple backticks or any formatting. "
        "Do NOT say anything before or after the diff. "
        "Return ONLY the code for the patch, starting with 'diff --git'. "
        "If you include anything else, the solution will be rejected. "
        "If you need to create a new file, use the correct unified diff format for new files, including '--- /dev/null', '+++ b/<filename>', and 'new file mode 100644'. "
        "Ensure the patch is valid and can be applied with 'git apply' without errors. The patch must end with a single newline and have no extra blank lines or trailing whitespace."
    )
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": user_prompt}
        ]
    )
    return response.choices[0].message.content 