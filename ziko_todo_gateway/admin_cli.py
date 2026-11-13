"""Offline administrative ACL setup. Never exposed over HTTP."""
import argparse
import os

from acl import DEFAULT_DB, init_db, create_project, grant, revoke, accessible_projects


def main() -> None:
    parser = argparse.ArgumentParser(description="ZikoTodo offline project ACL administration")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    sub = parser.add_subparsers(dest="action", required=True)

    p = sub.add_parser("create-project")
    p.add_argument("slug")
    p.add_argument("title")

    p = sub.add_parser("grant")
    p.add_argument("slug")
    p.add_argument("ha_user_id")
    p.add_argument("role", choices=["viewer", "editor", "manager"])

    p = sub.add_parser("revoke")
    p.add_argument("slug")
    p.add_argument("ha_user_id")

    p = sub.add_parser("list-access")
    p.add_argument("ha_user_id")

    args = parser.parse_args()
    # CLI is not a network endpoint. Access to the add-on's /data remains
    # a privileged host operation, with audit obligations for future releases.
    init_db(args.db)
    if args.action == "create-project":
        create_project(args.db, args.slug, args.title)
    elif args.action == "grant":
        grant(args.db, args.slug, args.ha_user_id, args.role)
    elif args.action == "revoke":
        revoke(args.db, args.slug, args.ha_user_id)
    else:
        for project in accessible_projects(args.db, args.ha_user_id):
            print(f"{project['slug']} {project['role']}")
    if args.action != "list-access":
        print("ACL updated")


if __name__ == "__main__":
    main()
