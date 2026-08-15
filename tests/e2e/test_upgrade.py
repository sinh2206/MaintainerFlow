import os
import subprocess
import uuid

import pytest

pytestmark = pytest.mark.e2e


def command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def psql(database: str, sql: str) -> str:
    return command(
        "docker",
        "compose",
        "exec",
        "-T",
        "db",
        "psql",
        "-U",
        "maintainerflow",
        "-d",
        database,
        "-Atc",
        sql,
    ).stdout.strip()


def migrate(database: str, *arguments: str) -> None:
    url = f"postgresql+asyncpg://maintainerflow:maintainerflow@db:5432/{database}"
    command(
        "docker",
        "compose",
        "run",
        "--rm",
        "--no-deps",
        "-e",
        f"MAINTAINERFLOW_DATABASE_URL={url}",
        "migrate",
        "alembic",
        *arguments,
    )


def test_cp4_database_upgrades_to_cp5_without_losing_delivery_issue_or_audit() -> None:
    if os.getenv("RUN_E2E") != "1":
        pytest.skip("set RUN_E2E=1 after starting Docker Compose")
    database = f"maintainerflow_upgrade_{uuid.uuid4().hex[:10]}"
    psql("postgres", f'CREATE DATABASE "{database}"')
    try:
        migrate(database, "upgrade", "0004_issue_repository_context")
        psql(
            database,
            """
            INSERT INTO github_installations (github_id) VALUES (9001);
            INSERT INTO repositories (github_id,installation_id,owner,name)
              SELECT 9002,id,'upgrade','fixture' FROM github_installations WHERE github_id=9001;
            INSERT INTO deliveries
              (github_delivery_id,repository_id,event_name,action,envelope,status,attempts,request_id)
              SELECT 'upgrade-delivery',id,'issues','opened','{}','completed',1,'upgrade-request'
              FROM repositories WHERE github_id=9002;
            INSERT INTO issue_analyses
              (repository_id,github_issue_id,issue_number,source_hash,classification,confidence,
               evidence_spans,priority,priority_score,label_suggestions,similar_issues,limitations,
               expires_at)
              SELECT id,9003,3,repeat('a',64),'bug',0.9,'[]','high',7.0,'[]','[]','[]',
                     now() + interval '1 day'
              FROM repositories WHERE github_id=9002;
            INSERT INTO audit_events
              (event_type,repository_id,issue_analysis_id,payload)
              SELECT 'issue.triage.suggested',r.id,i.id,'{}'
              FROM repositories r JOIN issue_analyses i ON i.repository_id=r.id
              WHERE r.github_id=9002;
            """,
        )
        before = psql(
            database,
            "SELECT (SELECT count(*) FROM deliveries),"
            "(SELECT count(*) FROM issue_analyses),(SELECT count(*) FROM audit_events);",
        )
        migrate(database, "upgrade", "head")
        after = psql(
            database,
            "SELECT (SELECT count(*) FROM deliveries),"
            "(SELECT count(*) FROM issue_analyses),(SELECT count(*) FROM audit_events),"
            "(SELECT count(*) FROM release_drafts);",
        )
        revision = psql(database, "SELECT version_num FROM alembic_version;")
        migrate(database, "downgrade", "0004_issue_repository_context")
        restored = psql(
            database,
            "SELECT (SELECT count(*) FROM deliveries),"
            "(SELECT count(*) FROM issue_analyses),(SELECT count(*) FROM audit_events);",
        )

        assert before == "1|1|1"
        assert after == "1|1|1|0"
        assert revision == "0005_release_assistant"
        assert restored == before
    finally:
        psql("postgres", f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
