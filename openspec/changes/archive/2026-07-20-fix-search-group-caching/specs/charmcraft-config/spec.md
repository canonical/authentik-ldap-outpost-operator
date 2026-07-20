## ADDED Requirements

### Requirement: Declare search group configuration option with correct default
The charm `charmcraft.yaml` MUST declare a string configuration option named `search_group` with a default value of `"authentik Admins"`.

#### Scenario: Configuration option is declared with correct default
- **WHEN** the charm metadata is parsed
- **THEN** the configuration contains `search_group` of type `string` with a default of `"authentik Admins"`
