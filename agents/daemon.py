import argparse
import sys
import os
import json
import time
from datetime import datetime
from agents.pipeline import Pipeline
from agents.base import get_agent_logger

logger = get_agent_logger("daemon")

def get_status_path():
    os.makedirs("outputs", exist_ok=True)
    return "outputs/daemon_status.json"

def read_status():
    path = get_status_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"status": "stopped", "pid": None, "last_run": None}

def write_status(status, pid=None, last_run=None, next_run=None):
    path = get_status_path()
    data = read_status()
    data["status"] = status
    if status == "stopped":
        data["pid"] = None
    elif pid is not None:
        data["pid"] = pid
    if last_run is not None:
        data["last_run"] = last_run
    if next_run is not None:
        data["next_run"] = next_run
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write daemon status: {e}")

def run_once(pdf_path=None, persona=None, source_platform=None, keyword=None):
    logger.info("Executing run-once daemon pipeline command.")
    write_status("running", pid=os.getpid())
    try:
        from agents.validation import create_default_context
        from agents.trend_analyst import TrendAnalystAgent
        from agents.copywriter import CopywriterAgent
        from agents.fact_checker import FactCheckerAgent
        from agents.publisher import PublisherAgent

        pipeline = Pipeline()
        pipeline.register(TrendAnalystAgent())
        pipeline.register(CopywriterAgent())
        pipeline.register(FactCheckerAgent())
        pipeline.register(PublisherAgent())

        context = create_default_context()
        if pdf_path:
            context["pdf_path"] = pdf_path
        if persona:
            context["persona"] = persona
        if source_platform:
            context["source_platform"] = source_platform
        if keyword:
            context["keyword"] = keyword
            
        result = pipeline.run(context)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        write_status("stopped", last_run=now_str)
        logger.info("run-once completed successfully.")
        return result
    except Exception as e:
        logger.error(f"Daemon run-once pipeline failed: {e}")
        write_status("stopped")
        raise e

def main():
    parser = argparse.ArgumentParser(description="Daemon coordinator CLI for Multi-Agent Auto-Blogging Backend")
    parser.add_argument("command", choices=["start", "stop", "status", "run-once"], help="Daemon command to execute")
    parser.add_argument("--pdf_path", help="Path to agenda PDF")
    parser.add_argument("--persona", choices=["health", "economy", "brandconnect"], help="Copywriter persona")
    parser.add_argument("--source_platform", choices=["daum", "nate"], help="Crawler source platform")
    parser.add_argument("--keyword", help="Target keyword")

    args = parser.parse_args()
    
    if args.command == "start":
        status_data = read_status()
        if status_data.get("status") == "running":
            logger.info("Daemon is already running.")
            print("Daemon is already running.")
            return
            
        logger.info("Starting daemon process.")
        write_status("running", pid=os.getpid(), next_run=(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        print("Daemon started.")
        
    elif args.command == "stop":
        logger.info("Stopping daemon process.")
        write_status("stopped", pid=None)
        print("Daemon stopped.")
        
    elif args.command == "status":
        status_data = read_status()
        print(json.dumps(status_data, indent=2))
        
    elif args.command == "run-once":
        try:
            run_once(args.pdf_path, args.persona, args.source_platform, args.keyword)
            print("Run-once execution successful.")
        except Exception as e:
            print(f"Run-once execution failed: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
