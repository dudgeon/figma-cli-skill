"""figma CLI dispatcher.

All subcommands emit JSON on stdout. Errors go to stderr as structured
JSON with a non-zero exit code. See output.py.
"""
from __future__ import annotations

import argparse
import sys

from . import output


def _global_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="figma",
        description="Read Figma mocks with full fidelity and manage Figma comments.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress progress hints on stderr.")
    parser.add_argument("--json", action="store_true", help="(default) JSON output on stdout.")
    parser.set_defaults(func=None)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = _global_parser()
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # whoami
    p = sub.add_parser("whoami", help="Verify the FIGMA_TOKEN works.")
    from .commands import whoami
    p.set_defaults(func=whoami.run)

    # resolve
    p = sub.add_parser("resolve", help="Classify a Figma URL and persist learned IDs.")
    p.add_argument("url")
    from .commands import resolve
    p.set_defaults(func=resolve.run)

    # refs
    p = sub.add_parser("refs", help="Browse the persistent ref file.")
    refs_sub = p.add_subparsers(dest="refs_command", metavar="<subcommand>")

    from .commands import refs_cmd
    rp = refs_sub.add_parser("list", help="List known refs.")
    rp.add_argument("--kind", choices=["team", "project", "file", "node"])
    rp.add_argument("--grep", help="Case-insensitive filter on name or id.")
    rp.set_defaults(func=refs_cmd.run_list)

    rp = refs_sub.add_parser("show", help="Show a single ref by URL or id.")
    rp.add_argument("identifier")
    rp.set_defaults(func=refs_cmd.run_show)

    rp = refs_sub.add_parser("forget", help="Remove a ref by URL or id.")
    rp.add_argument("identifier")
    rp.set_defaults(func=refs_cmd.run_forget)

    # file summary / page (M2)
    p = sub.add_parser("file", help="File-level operations.")
    file_sub = p.add_subparsers(dest="file_command", metavar="<subcommand>")

    from .commands import file as file_cmd
    fp = file_sub.add_parser("summary", help="Tier 1: pages + top-level frames.")
    fp.add_argument("url")
    fp.set_defaults(func=file_cmd.run_summary)

    fp = file_sub.add_parser("page", help="Tier 2: frames for a single page.")
    fp.add_argument("url")
    fp.add_argument("--page-id", help="Page node id (defaults to first page).")
    fp.set_defaults(func=file_cmd.run_page)

    # node read / assets (M2)
    p = sub.add_parser("node", help="Node-level operations.")
    node_sub = p.add_subparsers(dest="node_command", metavar="<subcommand>")

    from .commands import node as node_cmd
    np = node_sub.add_parser("read", help="Tier 3: lossless node payload.")
    np.add_argument("url")
    np.add_argument("--scale", type=int, default=2, choices=[1, 2, 3, 4])
    np.add_argument("--no-svg", action="store_true", help="Skip SVG render.")
    np.add_argument("--depth", type=int, help="Clamp tree depth (default: full).")
    np.set_defaults(func=node_cmd.run_read)

    np = node_sub.add_parser("assets", help="Tier 4: binary assets on demand.")
    np.add_argument("url")
    np.add_argument("--format", default="png", choices=["png", "svg", "pdf", "jpg"])
    np.add_argument("--scale", type=int, default=2, choices=[1, 2, 3, 4])
    np.set_defaults(func=node_cmd.run_assets)

    # comments (M3)
    p = sub.add_parser("comments", help="Read, reply to, create, and resolve Figma comments.")
    c_sub = p.add_subparsers(dest="comments_command", metavar="<subcommand>")

    from .commands import comments
    cp = c_sub.add_parser("list", help="List all comment threads in a file.")
    cp.add_argument("url")
    cp.add_argument("--unresolved", action="store_true")
    cp.add_argument("--node", dest="node_id", help="Filter by anchor node id.")
    cp.add_argument("--author", help="Filter by author handle (case-insensitive).")
    cp.set_defaults(func=comments.run_list)

    cp = c_sub.add_parser("reply", help="Reply to an existing comment thread.")
    cp.add_argument("comment_id", help="Parent comment id to reply to.")
    cp.add_argument("text")
    cp.add_argument("--file", dest="file_url", help="File URL (required if comment_id is ambiguous).")
    cp.set_defaults(func=comments.run_reply)

    cp = c_sub.add_parser("create", help="Create a new top-level comment anchored to a node.")
    cp.add_argument("url", help="Figma node URL (file+node).")
    cp.add_argument("text")
    cp.set_defaults(func=comments.run_create)

    cp = c_sub.add_parser("resolve", help="Mark a comment thread as resolved.")
    cp.add_argument("comment_id")
    cp.add_argument("--file", dest="file_url", help="File URL.")
    cp.set_defaults(func=comments.run_resolve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.quiet:
        output.set_quiet(True)

    if args.func is None:
        parser.print_help(sys.stderr)
        return 2

    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        sys.stderr.write("\ninterrupted\n")
        return 130


if __name__ == "__main__":
    sys.exit(main())
