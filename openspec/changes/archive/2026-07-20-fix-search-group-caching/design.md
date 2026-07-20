## Context

The `authentik-ldap-outpost-operator` provisions machine service accounts in Authentik for each consumer relation. To perform directory searches, these service accounts must belong to a designated search group. 
Currently, the default `search_group` value is set to an invalid group (`"authentik Admingroup"`), preventing integration searches from working out-of-the-box. Furthermore, to avoid querying the Authentik API on every single hook/charm invocation, the operator employs a peer metadata caching mechanism (tracking `last_base_dn`, `last_search_mode`, etc.). However, `search_group` is completely excluded from this cache. Adding reconciliation logic for `search_group` without tracking its changes would bypass the cache and trigger redundant API calls on every invocation.

Finally, if the configured `search_group` does not exist on the Authentik Server, the operator currently logs a warning but remains in `ActiveStatus`. This leads to a silent failure state where LDAP clients can authenticate but cannot perform searches.

## Goals / Non-Goals

**Goals:**
- Update the default `search_group` in `charmcraft.yaml` to `"authentik Admins"`.
- Extend the config metadata peer caching to track `last_search_group` alongside other config parameters.
- Provide a mechanism to gracefully update the group membership of existing service accounts when the `search_group` configuration option is updated, without generating redundant API queries.
- Enforce the existence of the `search_group` on the Authentik server and raise a `BlockedStatus` if it is missing.

**Non-Goals:**
- Automatically creating missing groups on the Authentik server instance.
- Synchronizing arbitrary user roles.

## Decisions

### Decision 1: Extend Peer Metadata Cache for `search_group`
We will track the configuration state of the search group in the peer relation databag using the key `last_search_group`.
- **Rationale**: Keeps the caching architecture consistent. If `last_search_group` matches the current `search_group` config option, we know that no group membership changes are needed, preventing redundant Authentik REST API requests.
- **Alternatives Considered**: Querying the Authentik group membership on every hook run (rejected because of performance degradation and API rate-limiting risks).

### Decision 2: Update Group Memberships of Existing Service Accounts On-Change
If the `search_group` configuration changes (`last_search_group != search_group` in `_verify_and_update_existing_resources`), we will retrieve the group UUID for the new search group and iterate over all active relation service accounts, calling the Authentik API client `add_user_to_group` to add them to the new group.
- **Rationale**: Ensures existing consumer relations continue working seamlessly when configuration transitions occur.
- **Alternatives Considered**: Deleting and recreating all service accounts (rejected as too disruptive and complex).

### Decision 3: Enforce Search Group Existence and Raise BlockedStatus
We will update `_on_collect_status` and the reconciliation loop to verify that the group exists on the Authentik server. If `client.get_group_by_name(search_group_name)` returns `None` (not found), we will set a flag in the peer relation databag (or in memory) and surface a `BlockedStatus("LDAP search group '<group>' not found in Authentik")`.
- **Rationale**: Elevates silent configuration errors to visible Juju statuses, prompting the administrator to create the group in the Authentik UI or correct the configuration name.
- **Alternatives Considered**: Remaining in `ActiveStatus` with a log warning (rejected because silent search failures degrade operational reliability).

## Risks / Trade-offs

- **[Risk]** The new search group does not exist on the Authentik Server.
- **[Mitigation]** Surfacing a `BlockedStatus` ensures the administrator can immediately see and rectify the problem, rather than experiencing silent client failures.
