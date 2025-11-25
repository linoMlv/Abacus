import subprocess
import shutil
import os
import sys

def run_command(command, cwd=None):
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, cwd=cwd)
    if result.returncode != 0:
        print(f"Error running command: {command}")
        sys.exit(1)

def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "backend")
    static_dir = os.path.join(backend_dir, "static")

    print("Updating repository...")
    run_command("git pull", cwd=root_dir)

    print("Building Frontend...")
    run_command("npm run build", cwd=root_dir)

    print("Copying build artifacts to backend/static...")
    if os.path.exists(static_dir):
        shutil.rmtree(static_dir)
    
    dist_dir = os.path.join(root_dir, "dist")
    if not os.path.exists(dist_dir):
        print("Error: dist directory not found. Build failed?")
        sys.exit(1)
        
    shutil.copytree(dist_dir, static_dir)
    print("Artifacts copied.")

    print("Starting Production Server...")
    os.environ["PYTHONPATH"] = backend_dir
    run_command("python cli.py start --host 0.0.0.0 --port 9874 --no-reload", cwd=backend_dir)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
