import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
JOB_START = re.compile(r"^  (?=[a-z][a-z-]*:$)", re.MULTILINE)


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def workflow_jobs(name: str) -> dict[str, str]:
    jobs = workflow(name).split("\njobs:\n", 1)[1]
    blocks = [block for block in JOB_START.split(jobs) if block.strip()]
    return {block.split(":", 1)[0]: block for block in blocks}
