import argparse
import asyncio
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


def retarget_insert(sql: str, source_table: str, staging_table: str) -> str:
    pattern = re.compile(
        rf"^(\s*INSERT\s+INTO\s+)(?:\"public\"\.)?\"?{re.escape(source_table)}\"?",
        flags=re.IGNORECASE,
    )
    rewritten, replacements = pattern.subn(rf"\1{staging_table}", sql.strip(), count=1)
    if replacements != 1:
        raise ValueError(f"Expected an INSERT INTO {source_table} statement")
    return rewritten


async def import_users(connection, path: Path) -> None:
    statement = retarget_insert(path.read_text(encoding="utf-8-sig"), "users", "legacy_bot_users")
    await connection.execute(
        text(
            """
            CREATE TEMP TABLE legacy_bot_users (
                user_id bigint PRIMARY KEY,
                username text,
                first_name text,
                created_at timestamp without time zone
            ) ON COMMIT DROP
            """
        )
    )
    await connection.exec_driver_sql(statement)
    await connection.execute(
        text(
            """
            INSERT INTO telegram_users (
                id, telegram_id, username, first_name, last_name, language_code,
                is_bot, created_at, last_seen_at
            )
            SELECT
                md5('legacy-telegram-user:' || user_id::text)::uuid,
                user_id,
                username,
                first_name,
                NULL,
                NULL,
                false,
                created_at AT TIME ZONE 'UTC',
                created_at AT TIME ZONE 'UTC'
            FROM legacy_bot_users
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = COALESCE(EXCLUDED.username, telegram_users.username),
                first_name = COALESCE(EXCLUDED.first_name, telegram_users.first_name),
                last_seen_at = GREATEST(telegram_users.last_seen_at, EXCLUDED.last_seen_at)
            """
        )
    )


async def import_applications(connection, path: Path) -> None:
    statement = retarget_insert(
        path.read_text(encoding="utf-8-sig"), "applications", "legacy_bot_applications"
    )
    await connection.execute(
        text(
            """
            CREATE TEMP TABLE legacy_bot_applications (
                id integer PRIMARY KEY,
                user_id bigint,
                username text,
                text text,
                status text,
                created_at timestamp without time zone
            ) ON COMMIT DROP
            """
        )
    )
    await connection.exec_driver_sql(statement)
    await connection.execute(
        text(
            """
            WITH normalized AS (
                SELECT
                    application.id,
                    application.user_id,
                    application.username,
                    application.text,
                    application.created_at,
                    LEFT(
                        COALESCE(
                            NULLIF(telegram_user.first_name, ''),
                            NULLIF(application.username, ''),
                            'Telegram ' || application.user_id::text
                        ),
                        200
                    ) AS display_name,
                    CASE lower(COALESCE(application.status, 'pending'))
                        WHEN 'approved' THEN 'Approved'
                        WHEN 'accepted' THEN 'Approved'
                        WHEN 'rejected' THEN 'Rejected'
                        WHEN 'declined' THEN 'Rejected'
                        ELSE 'Under review'
                    END AS crm_status
                FROM legacy_bot_applications application
                LEFT JOIN telegram_users telegram_user
                    ON telegram_user.telegram_id = application.user_id
                WHERE application.user_id IS NOT NULL
            )
            INSERT INTO candidates (
                id, name, initials, role, company, status, wave, code, summary,
                expertise, country, telegram, telegram_id, person_key, external_id,
                questionnaire_answers, social_links, projects, achievements,
                manager_comments, decision, member_profile, purchase_confirmed,
                product, source, stage, applied_at, created_at
            )
            SELECT
                'legacy-bot-' || id::text,
                display_name,
                upper(left(display_name, 2)),
                '',
                '',
                crm_status,
                '',
                NULL,
                COALESCE(text, ''),
                '',
                '',
                CASE
                    WHEN username IS NULL OR username = '' THEN 'tg:' || user_id::text
                    ELSE '@' || ltrim(username, '@')
                END,
                user_id::text,
                'tg:' || user_id::text,
                'legacy-bot:' || id::text,
                jsonb_build_object('legacyApplication', COALESCE(text, '')),
                '{}'::jsonb,
                '[]'::jsonb,
                '[]'::jsonb,
                '[]'::jsonb,
                jsonb_build_object('legacyStatus', crm_status),
                NULL,
                false,
                '',
                'Telegram bot',
                'purchase',
                created_at AT TIME ZONE 'UTC',
                created_at AT TIME ZONE 'UTC'
            FROM normalized
            ON CONFLICT (external_id) DO NOTHING
            """
        )
    )


async def run(users_path: Path, applications_path: Path | None) -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.begin() as connection:
            await import_users(connection, users_path)
            if applications_path is not None:
                await import_applications(connection, applications_path)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import data from the legacy Telegram bot SQL export")
    parser.add_argument("--users", type=Path, required=True, help="Path to users_rows.sql")
    parser.add_argument("--applications", type=Path, help="Optional path to applications_rows.sql")
    args = parser.parse_args()
    if not args.users.is_file():
        parser.error(f"Users export not found: {args.users}")
    if args.applications is not None and not args.applications.is_file():
        parser.error(f"Applications export not found: {args.applications}")
    asyncio.run(run(args.users, args.applications))
    print("Legacy Telegram bot data imported successfully")


if __name__ == "__main__":
    main()
