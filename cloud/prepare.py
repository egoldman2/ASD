"""Build a cloud source bundle without changing the local Release 1 layout."""

import argparse
from pathlib import Path
import re
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
FEATURES = {
    "student-Chufeng": "/catalogue/",
    "student-Ryan_Nolan": "/inventory/",
    "student-Ethan Ting": "/account/",
    "student-Howard": "/orders/",
    "student-Ethan Goldman": "/support/",
}
ROUTES = {
    "8000": "/assets", "8001": "/catalogue", "8002": "/inventory",
    "8003": "/account", "8004": "/orders", "8005": "/support",
    "5000": "", "6002": "/account-api", "8102": "/inventory-api",
}
SOURCE_SUFFIXES = {".py", ".js", ".html", ".css", ".sql", ".txt", ".conf", ".yml", ".sh", ".template"}


def web_content(content):
    for port, route in ROUTES.items():
        old = f"http://localhost:{port}"
        content = content.replace(quote(old, safe=""), quote(route, safe=""))
        if port == "8000":
            content = content.replace(old + "/css/", "/assets/css/")
            content = content.replace(old + "/js/", "/assets/js/")
            content = content.replace(old, "/")
        else:
            content = content.replace(old, route)
    return content


def prepare(destination, source=ROOT):
    source, destination = source.resolve(), destination.resolve()
    if destination == source or source.is_relative_to(destination):
        raise ValueError("Build destination must not contain the source repository.")
    if destination.exists():
        raise ValueError("Use a fresh destination; existing build directories are never deleted.")
    destination.mkdir(parents=True)
    roots = [source / name for name in (*FEATURES, "shared", "cloud", "ai-services")]
    files = [source / name for name in ("app.py", "requirements.txt", ".dockerignore")]
    for root in roots:
        files.extend(root.rglob("*"))
    for path in sorted(files):
        relative = path.relative_to(source)
        if (
            not path.is_file() or path.is_symlink()
            or any(part.startswith(".") or part == "__pycache__" for part in relative.parts[:-1])
            or (path.suffix not in SOURCE_SUFFIXES and not path.name.startswith("Dockerfile") and path.name != ".dockerignore")
            or path.name.startswith(".env")
            or "chroma" in relative.parts
        ):
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        content = path.read_text(encoding="utf-8")
        is_web = "frontend" in relative.parts or relative.parts[0] == "shared"
        if is_web and path.suffix in {".html", ".js", ".conf"}:
            content = web_content(content)
        if "support_backend" in relative.parts and path.suffix == ".html":
            content = web_content(content)
        if path.suffix == ".html" and "frontend" in relative.parts:
            content = content.replace("<head>", f'<head>\n    <meta name="asd-cloud" content="true">\n    <base href="{FEATURES[relative.parts[0]]}">', 1)
        if relative.as_posix() == "shared/js/site-header.js":
            content = content.replace('url.pathname === "/css/styles.css"', 'url.pathname === "/assets/css/styles.css"')
        if relative.as_posix() == "shared/index.html":
            content = content.replace("Release 0", "Release 2")
            content = content.replace("<head>", '<head>\n    <meta name="asd-cloud" content="true">', 1)
            content = content.replace("AI-Powered Online Marketplace", "Online Marketplace")
            content = content.replace("Use AI-assisted support for shopping questions.", "Get help with shopping questions.")
            content = content.replace('<div class="heroText">', '<div class="heroText">\n          <p class="heroDescription">AI assistants are unavailable in this hosted demo.</p>', 1)
        target.write_text(content, encoding="utf-8")
    # Cloud AI is disabled; none of the application APIs need a Chroma index.
    requirements = destination / "requirements.txt"
    lines = [line for line in requirements.read_text().splitlines() if not line.lower().startswith("chromadb")]
    requirements.write_text("\n".join(lines) + "\ngunicorn==23.0.0\n")
    for directory in (destination / "shared", *(destination / name / "frontend" for name in FEATURES)):
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".html", ".js"} and re.search(r"https?://(?:localhost|127\.0\.0\.1)", path.read_text()):
                raise ValueError(f"Unmapped browser-local URL in {path.relative_to(destination)}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    print(prepare(arguments.destination))
