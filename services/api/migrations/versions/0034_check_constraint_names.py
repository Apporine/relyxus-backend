"""Give CHECK constraints the names the models declare.

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-15

Earlier migrations passed full names ("ck_<table>_<name>") to CHECK constraints while the
metadata naming convention ("ck_%(table_name)s_%(constraint_name)s") was applied on top,
so 66 constraints were created as "ck_<table>_ck_<table>_<name>", long ones truncated to
a hash. Behaviour is unchanged; only the names, which appear in error messages, were
wrong. This renames each one to its model name when it still has the doubled name, so it
is safe on any database built by migrations 0001-0033. New migrations name constraints
with `op.f(...)` so the convention is not applied twice; a test keeps database and model
names identical.

Rollout: metadata-only renames (brief ACCESS EXCLUSIVE lock per table). Rollback plan:
downgrade restores the previous names.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (table, name created by migrations 0001-0033, name declared by the model)
_RENAMES: tuple[tuple[str, str, str], ...] = (
    (
        "organizations",
        "ck_organizations_ck_organizations_deployment_mode",
        "ck_organizations_deployment_mode",
    ),
    ("users", "ck_users_ck_users_status", "ck_users_status"),
    ("audit_events", "ck_audit_events_ck_audit_events_actor_type", "ck_audit_events_actor_type"),
    ("audit_events", "ck_audit_events_ck_audit_events_outcome", "ck_audit_events_outcome"),
    (
        "audit_events",
        "ck_audit_events_ck_audit_events_sequence_positive",
        "ck_audit_events_sequence_positive",
    ),
    (
        "configuration_versions",
        "ck_configuration_versions_ck_configuration_versions_source",
        "ck_configuration_versions_source",
    ),
    (
        "configuration_versions",
        "ck_configuration_versions_ck_configuration_versions_object_type",
        "ck_configuration_versions_object_type",
    ),
    (
        "configuration_versions",
        "ck_configuration_versions_ck_configuration_versions_ver_43c2",
        "ck_configuration_versions_version_positive",
    ),
    ("workspaces", "ck_workspaces_ck_workspaces_key_format", "ck_workspaces_key_format"),
    (
        "custom_field_definitions",
        "ck_custom_field_definitions_ck_custom_field_definitions_d7bb",
        "ck_custom_field_definitions_key_format",
    ),
    (
        "custom_field_definitions",
        "ck_custom_field_definitions_ck_custom_field_definitions_2445",
        "ck_custom_field_definitions_condition_object",
    ),
    (
        "custom_field_definitions",
        "ck_custom_field_definitions_ck_custom_field_definitions_ce5a",
        "ck_custom_field_definitions_required_at_stage",
    ),
    (
        "custom_field_definitions",
        "ck_custom_field_definitions_ck_custom_field_definitions_d9ba",
        "ck_custom_field_definitions_version_positive",
    ),
    (
        "custom_field_definitions",
        "ck_custom_field_definitions_ck_custom_field_definitions_7252",
        "ck_custom_field_definitions_label_length",
    ),
    (
        "custom_field_definitions",
        "ck_custom_field_definitions_ck_custom_field_definitions_aaa7",
        "ck_custom_field_definitions_options_array",
    ),
    (
        "custom_field_definitions",
        "ck_custom_field_definitions_ck_custom_field_definitions_df95",
        "ck_custom_field_definitions_data_type",
    ),
    (
        "incident_types",
        "ck_incident_types_ck_incident_types_default_visibility",
        "ck_incident_types_default_visibility",
    ),
    (
        "incident_types",
        "ck_incident_types_ck_incident_types_key_format",
        "ck_incident_types_key_format",
    ),
    (
        "incident_types",
        "ck_incident_types_ck_incident_types_default_severity_allowed",
        "ck_incident_types_default_severity_allowed",
    ),
    (
        "incident_types",
        "ck_incident_types_ck_incident_types_version_positive",
        "ck_incident_types_version_positive",
    ),
    (
        "incident_types",
        "ck_incident_types_ck_incident_types_name_length",
        "ck_incident_types_name_length",
    ),
    (
        "incident_types",
        "ck_incident_types_ck_incident_types_default_severity",
        "ck_incident_types_default_severity",
    ),
    (
        "incident_types",
        "ck_incident_types_ck_incident_types_allowed_severities__3d80",
        "ck_incident_types_allowed_severities_not_empty",
    ),
    ("teams", "ck_teams_ck_teams_key_format", "ck_teams_key_format"),
    ("teams", "ck_teams_ck_teams_name_length", "ck_teams_name_length"),
    (
        "workspace_memberships",
        "ck_workspace_memberships_ck_workspace_memberships_role",
        "ck_workspace_memberships_role",
    ),
    (
        "incidents",
        "ck_incidents_ck_incidents_declared_when_past_triage",
        "ck_incidents_declared_when_past_triage",
    ),
    ("incidents", "ck_incidents_ck_incidents_number_positive", "ck_incidents_number_positive"),
    ("incidents", "ck_incidents_ck_incidents_merged_has_target", "ck_incidents_merged_has_target"),
    (
        "incidents",
        "ck_incidents_ck_incidents_not_merged_into_self",
        "ck_incidents_not_merged_into_self",
    ),
    (
        "incidents",
        "ck_incidents_ck_incidents_impact_not_after_detection",
        "ck_incidents_impact_not_after_detection",
    ),
    (
        "incidents",
        "ck_incidents_ck_incidents_acknowledged_has_actor",
        "ck_incidents_acknowledged_has_actor",
    ),
    ("incidents", "ck_incidents_ck_incidents_closed_has_time", "ck_incidents_closed_has_time"),
    ("incidents", "ck_incidents_ck_incidents_type_has_version", "ck_incidents_type_has_version"),
    ("incidents", "ck_incidents_ck_incidents_visibility", "ck_incidents_visibility"),
    ("services", "ck_services_ck_services_key_format", "ck_services_key_format"),
    ("services", "ck_services_ck_services_name_length", "ck_services_name_length"),
    ("services", "ck_services_ck_services_environment_format", "ck_services_environment_format"),
    ("services", "ck_services_ck_services_labels_object", "ck_services_labels_object"),
    ("services", "ck_services_ck_services_tier", "ck_services_tier"),
    (
        "team_role_grants",
        "ck_team_role_grants_ck_team_role_grants_role",
        "ck_team_role_grants_role",
    ),
    (
        "incident_access_grants",
        "ck_incident_access_grants_ck_incident_access_grants_exa_794b",
        "ck_incident_access_grants_exactly_one_grantee",
    ),
    (
        "incident_access_grants",
        "ck_incident_access_grants_ck_incident_access_grants_role",
        "ck_incident_access_grants_role",
    ),
    (
        "incident_access_grants",
        "ck_incident_access_grants_ck_incident_access_grants_rea_aae2",
        "ck_incident_access_grants_reason_length",
    ),
    (
        "incident_links",
        "ck_incident_links_ck_incident_links_not_self",
        "ck_incident_links_not_self",
    ),
    (
        "incident_links",
        "ck_incident_links_ck_incident_links_link_type",
        "ck_incident_links_link_type",
    ),
    (
        "incident_reviews",
        "ck_incident_reviews_ck_incident_reviews_text_length",
        "ck_incident_reviews_text_length",
    ),
    (
        "incident_reviews",
        "ck_incident_reviews_ck_incident_reviews_state",
        "ck_incident_reviews_state",
    ),
    (
        "incident_role_assignments",
        "ck_incident_role_assignments_ck_incident_role_assignments_role",
        "ck_incident_role_assignments_role",
    ),
    (
        "incident_role_handoffs",
        "ck_incident_role_handoffs_ck_incident_role_handoffs_role",
        "ck_incident_role_handoffs_role",
    ),
    (
        "incident_role_handoffs",
        "ck_incident_role_handoffs_ck_incident_role_handoffs_can_88d3",
        "ck_incident_role_handoffs_cancelled_has_time",
    ),
    (
        "incident_role_handoffs",
        "ck_incident_role_handoffs_ck_incident_role_handoffs_state",
        "ck_incident_role_handoffs_state",
    ),
    (
        "incident_role_handoffs",
        "ck_incident_role_handoffs_ck_incident_role_handoffs_dif_806c",
        "ck_incident_role_handoffs_different_people",
    ),
    (
        "incident_role_handoffs",
        "ck_incident_role_handoffs_ck_incident_role_handoffs_acc_9b4e",
        "ck_incident_role_handoffs_accepted_has_time",
    ),
    (
        "incident_tasks",
        "ck_incident_tasks_ck_incident_tasks_priority",
        "ck_incident_tasks_priority",
    ),
    (
        "incident_tasks",
        "ck_incident_tasks_ck_incident_tasks_cancelled_has_reason",
        "ck_incident_tasks_cancelled_has_reason",
    ),
    ("incident_tasks", "ck_incident_tasks_ck_incident_tasks_status", "ck_incident_tasks_status"),
    (
        "incident_tasks",
        "ck_incident_tasks_ck_incident_tasks_done_has_completion",
        "ck_incident_tasks_done_has_completion",
    ),
    (
        "incident_tasks",
        "ck_incident_tasks_ck_incident_tasks_title_length",
        "ck_incident_tasks_title_length",
    ),
    ("incident_tasks", "ck_incident_tasks_ck_incident_tasks_source", "ck_incident_tasks_source"),
    (
        "incident_follow_ups",
        "ck_incident_follow_ups_ck_incident_follow_ups_source",
        "ck_incident_follow_ups_source",
    ),
    (
        "incident_follow_ups",
        "ck_incident_follow_ups_ck_incident_follow_ups_source_ta_ce88",
        "ck_incident_follow_ups_source_task_matches",
    ),
    (
        "incident_follow_ups",
        "ck_incident_follow_ups_ck_incident_follow_ups_title_length",
        "ck_incident_follow_ups_title_length",
    ),
    (
        "incident_follow_ups",
        "ck_incident_follow_ups_ck_incident_follow_ups_cancelled_fca5",
        "ck_incident_follow_ups_cancelled_has_reason",
    ),
    (
        "incident_follow_ups",
        "ck_incident_follow_ups_ck_incident_follow_ups_status",
        "ck_incident_follow_ups_status",
    ),
    (
        "incident_follow_ups",
        "ck_incident_follow_ups_ck_incident_follow_ups_done_has__4e3f",
        "ck_incident_follow_ups_done_has_completion",
    ),
)


def _rename(table: str, current: str, target: str) -> None:
    # Only the constant names in _RENAMES reach this statement, never external input.
    op.execute(
        "DO $$ BEGIN "  # noqa: S608
        "IF EXISTS (SELECT 1 FROM pg_constraint "
        f"WHERE conrelid = '{table}'::regclass AND conname = '{current}') THEN "
        f"ALTER TABLE {table} RENAME CONSTRAINT {current} TO {target}; "
        "END IF; END $$"
    )


def upgrade() -> None:
    for table, doubled, declared in _RENAMES:
        _rename(table, doubled, declared)


def downgrade() -> None:
    for table, doubled, declared in _RENAMES:
        _rename(table, declared, doubled)
