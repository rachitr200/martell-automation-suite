"""
python -m copilot_api.cli build data/sample_conversations.json data/playbook.json
python -m copilot_api.cli serve data/playbook.json [--port 8787]
"""

import argparse
import json

from copilot_api.patterns import build_playbook
from copilot_api.server import make_server


def main(argv=None) -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("conversations"); b.add_argument("out")
    s = sub.add_parser("serve"); s.add_argument("playbook"); s.add_argument("--port", type=int, default=8787)
    args = p.parse_args(argv)

    if args.cmd == "build":
        playbook = build_playbook(json.load(open(args.conversations)))
        json.dump(playbook, open(args.out, "w"), indent=2)
        print(f"wrote {args.out}: {playbook['stats']}, {len(playbook['top_phrases'])} phrases")
    else:
        server = make_server(json.load(open(args.playbook)), port=args.port)
        print(f"listening on http://127.0.0.1:{args.port}  (Ctrl+C to stop)")
        server.serve_forever()


if __name__ == "__main__":
    main()
