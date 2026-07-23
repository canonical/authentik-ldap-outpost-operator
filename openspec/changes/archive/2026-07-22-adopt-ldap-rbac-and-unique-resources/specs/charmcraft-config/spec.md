## REMOVED Requirements

### Requirement: Declare search group configuration option with correct default
**Reason**: Full-directory search is now granted through a charm-managed Authentik
role that assigns the provider-scoped `search_full_directory` permission
(Authentik >= 2024.8), so the `search_group` option has no effect.
**Migration**: None. The charm is pre-release; the `search_group` option is removed
outright from `charmcraft.yaml` and runtime reconciliation no longer reads it or
stores `last_search_group` peer metadata.
