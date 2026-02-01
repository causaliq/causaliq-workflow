# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Nothing yet

### Changed
- Nothing yet

### Deprecated
- Nothing yet

### Removed
- Nothing yet

### Fixed
- Nothing yet

### Security
- Nothing yet

## [0.1.0] Workflow Foundations - 2026-02-01

### Added
- Initial project structure and scaffolding with environment setup, CLI, pytest testing and CI testing on GitHub
- Framework for plug-in actions with auto-discovery system
- YAML workflow parsing with matrix expansion and step execution
- JSON Schema validation with clear error reporting
- Template variable validation for workflow files - automatic validation of `{{variable}}` patterns against available context (workflow properties + matrix variables) with clear error messages for unknown variables
- Support for Python 3.9, 3.10, 3.11, 3.12, and 3.13
- `cqflow` short form command alias for `causaliq-workflow`
- `CausalIQAction` base class for implementing custom actions
- Comprehensive logging system with configurable log levels
- 100% test coverage
